from __future__ import annotations

from dataclasses import dataclass
import platform
import sys


@dataclass(frozen=True)
class CudaDiagnostics:
    python_version: str
    platform: str
    torch_available: bool
    torch_version: str | None
    torch_cuda_version: str | None
    cuda_available: bool
    gpu_name: str | None
    gpu_total_vram_bytes: int | None
    error: str | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def collect_cuda_diagnostics() -> CudaDiagnostics:
    try:
        import torch
    except Exception as exc:
        return CudaDiagnostics(
            python_version=sys.version.replace("\n", " "),
            platform=platform.platform(),
            torch_available=False,
            torch_version=None,
            torch_cuda_version=None,
            cuda_available=False,
            gpu_name=None,
            gpu_total_vram_bytes=None,
            error=f"torch import failed: {exc}",
        )
    cuda_available = bool(torch.cuda.is_available())
    gpu_name = None
    gpu_memory = None
    if cuda_available:
        idx = torch.cuda.current_device()
        gpu_name = torch.cuda.get_device_name(idx)
        gpu_memory = int(torch.cuda.get_device_properties(idx).total_memory)
    return CudaDiagnostics(
        python_version=sys.version.replace("\n", " "),
        platform=platform.platform(),
        torch_available=True,
        torch_version=getattr(torch, "__version__", None),
        torch_cuda_version=getattr(torch.version, "cuda", None),
        cuda_available=cuda_available,
        gpu_name=gpu_name,
        gpu_total_vram_bytes=gpu_memory,
        error=None,
    )

