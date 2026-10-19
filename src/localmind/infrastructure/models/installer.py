"""Download a pinned, checksummed ONNX embedding model package."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from localmind.domain.models import ModelInstallCancelled, ModelInstallError

MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
MODEL_VERSION = "minilm-l6-v2-o4"
MODEL_SOURCE = f"https://huggingface.co/{MODEL_ID}/tree/{MODEL_REVISION}"
DOWNLOAD_CHUNK_SIZE = 256 * 1024
DOWNLOAD_TIMEOUT_SECONDS = 30


@dataclass(frozen=True, slots=True)
class ModelAsset:
    remote_path: str
    local_path: str
    size_bytes: int
    sha256: str

    @property
    def url(self) -> str:
        return (
            f"https://huggingface.co/{MODEL_ID}/resolve/{MODEL_REVISION}/"
            f"{self.remote_path}?download=true"
        )


MODEL_ASSETS = (
    ModelAsset(
        "onnx/model_O4.onnx",
        "onnx/model_O4.onnx",
        45_212_349,
        "1667d7f3ba669048b13a96ee3a44456d5e42c8f44588ae8b603430e16160c485",
    ),
    ModelAsset(
        "tokenizer.json",
        "tokenizer.json",
        466_247,
        "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037",
    ),
    ModelAsset(
        "1_Pooling/config.json",
        "1_Pooling/config.json",
        190,
        "4be450dde3b0273bb9787637cfbd28fe04a7ba6ab9d36ac48e92b11e350ffc23",
    ),
)


class PinnedHuggingFaceModelInstaller:
    """Install only the built-in model assets and verify each SHA-256 digest."""

    def __init__(self, data_directory: Path | None = None) -> None:
        self._data_directory = data_directory or self._default_data_directory()
        self._install_path = self._data_directory / "models" / MODEL_VERSION

    @property
    def install_path(self) -> Path:
        return self._install_path

    @property
    def total_size(self) -> int:
        return sum(asset.size_bytes for asset in MODEL_ASSETS)

    @staticmethod
    def _default_data_directory() -> Path:
        if os.name == "nt":
            base = os.environ.get("LOCALAPPDATA")
            return Path(base) / "LocalMind" if base else Path.home() / "AppData/Local/LocalMind"
        if sys.platform == "darwin":
            return Path.home() / "Library/Application Support/LocalMind"
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home and Path(xdg_data_home).is_absolute():
            return Path(xdg_data_home) / "localmind"
        return Path.home() / ".local/share/localmind"

    def is_installed(self) -> bool:
        marker_path = self._install_path / "install.json"
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if not isinstance(marker, dict):
                return False
            if marker.get("model") != MODEL_ID or marker.get("revision") != MODEL_REVISION:
                return False
            return all(self._verify_asset(self._install_path / asset.local_path, asset) for asset in MODEL_ASSETS)
        except (OSError, ValueError, TypeError):
            return False

    def install(
        self,
        progress: Callable[[int, int], None],
        cancel_event: threading.Event,
    ) -> Path:
        if self.is_installed():
            progress(self.total_size, self.total_size)
            return self._install_path
        if self._install_path.exists():
            raise ModelInstallError(
                "An incomplete model folder already exists. Remove the LocalMind model folder "
                "shown below, then try the download again."
            )

        try:
            self._install_path.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(prefix=f".{MODEL_VERSION}-download-", dir=self._install_path.parent)
            )
        except OSError as exc:
            raise ModelInstallError("LocalMind could not create its model storage folder.") from exc

        downloaded_before_asset = 0
        try:
            for asset in MODEL_ASSETS:
                if cancel_event.is_set():
                    raise ModelInstallCancelled("Model download cancelled.")
                destination = staging / asset.local_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                self._download_asset(
                    asset,
                    destination,
                    downloaded_before_asset,
                    progress,
                    cancel_event,
                )
                downloaded_before_asset += asset.size_bytes

            marker = {
                "model": MODEL_ID,
                "revision": MODEL_REVISION,
                "version": MODEL_VERSION,
                "source": MODEL_SOURCE,
                "license": "Apache-2.0",
                "assets": [
                    {"path": asset.local_path, "size": asset.size_bytes, "sha256": asset.sha256}
                    for asset in MODEL_ASSETS
                ],
            }
            (staging / "install.json").write_text(
                json.dumps(marker, indent=2) + "\n",
                encoding="utf-8",
            )
            if cancel_event.is_set():
                raise ModelInstallCancelled("Model download cancelled.")
            if self._install_path.exists():
                raise ModelInstallError("The model folder changed during installation. Please retry.")
            os.replace(staging, self._install_path)
        except ModelInstallError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise ModelInstallError(
                "The model download did not finish. Check your connection and free disk space, then retry."
            ) from exc
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise ModelInstallError("LocalMind could not complete model setup.") from exc
        progress(self.total_size, self.total_size)
        return self._install_path

    def _download_asset(
        self,
        asset: ModelAsset,
        destination: Path,
        downloaded_before_asset: int,
        progress: Callable[[int, int], None],
        cancel_event: threading.Event,
    ) -> None:
        request = Request(
            asset.url,
            headers={"User-Agent": "LocalMind/0.1 model-setup"},
        )
        digest = hashlib.sha256()
        written = 0
        try:
            with urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
                if not response.geturl().startswith("https://"):
                    raise ModelInstallError("The model server returned an insecure download URL.")
                with destination.open("xb") as output:
                    while True:
                        if cancel_event.is_set():
                            raise ModelInstallCancelled("Model download cancelled.")
                        chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > asset.size_bytes:
                            raise ModelInstallError("A model file exceeded its expected size.")
                        digest.update(chunk)
                        output.write(chunk)
                        progress(downloaded_before_asset + written, self.total_size)
        except ModelInstallError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ModelInstallError("A model file could not be downloaded from the pinned source.") from exc

        if written != asset.size_bytes or digest.hexdigest() != asset.sha256:
            raise ModelInstallError(
                "A model file failed its integrity check. The package was discarded; retry later."
            )

    @staticmethod
    def _verify_asset(path: Path, asset: ModelAsset) -> bool:
        try:
            if path.stat().st_size != asset.size_bytes:
                return False
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(DOWNLOAD_CHUNK_SIZE):
                    digest.update(chunk)
            return digest.hexdigest() == asset.sha256
        except OSError:
            return False
