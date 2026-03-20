# SMPL → Holosoma Data Converter

**[中文文档](README_CN.md) | English**

Convert standard **SMPL parameter data** (`body_pose` + `global_orient` + `betas` + `transl`) into the **SMPLH 52-joint global 3D position** format required by [Holosoma Motion Retargeting](https://github.com/amazon-far/holosoma), enabling humanoid robot motion retargeting.

---

## Background

[Holosoma](https://github.com/amazon-far/holosoma) is an open-source humanoid robot motion retargeting framework by Amazon, supporting motion transfer to humanoid robots such as the Unitree G1. Its retargeting module requires input data in the **OMOMO_new / InterMimic format** — a `.pt` file containing **SMPLH 52-joint global 3D positions**.

The input to this tool is standard **SMPL parameters** (24 joints: `body_pose`, `global_orient`, `betas`, `transl`), which can come from any SMPL-compatible system (e.g., HMR4D, CLIFF, 4D-Humans, etc.).

The following differences must be resolved before retargeting can proceed:

| Item | SMPL Input | Holosoma Requirement |
|------|-----------|----------------------|
| Joint count | 24 (SMPL) | 52 (SMPLH) |
| Data form | Rotation parameters (axis-angle) | Global 3D joint positions (meters) |
| Coordinate system | Y-up | Z-up |
| Joint order | smplx standard order | holosoma SMPLH_DEMO_JOINTS order |
| File format | dict (multiple fields) | `[T, 591]` float32 tensor |

---

## Pipeline

```
SMPL Parameters (any source)
    │
    │  body_pose (T,63) + global_orient (T,3) + betas (T,10) + transl (T,3)
    ▼
SMPLH Forward Kinematics  (via smplx)
    │
    │  52 joint global 3D positions  (T, 52, 3)
    ▼
Joint Reordering
    │
    │  smplx standard order → holosoma SMPLH_DEMO_JOINTS order
    ▼
Coordinate Transform
    │
    │  Y-up → Z-up :  (x, y, z) → (z, x, y)
    ▼
Pack into [T, 591] tensor
    │
    │  cols 162-317: joint positions (core data)
    │  other cols:   zero-padded / identity object pose
    ▼
Output:  holosoma_ready.pt  ← ready for holosoma retargeting
```

---

## Output Format

The output is a `[T, 591]` float32 tensor, fully compatible with Holosoma's `demo_data/OMOMO_new` dataset:

| Column range | Dims | Content |
|--------------|------|---------|
| 0 – 161 | 162 | Zeros (unused by holosoma) |
| **162 – 317** | **156 = 52×3** | **52 SMPLH joint global 3D positions, Z-up, in meters** |
| 318 – 324 | 7 | Object pose `[x,y,z,qx,qy,qz,qw]` (identity when no object) |
| 325 – 590 | 266 | Zeros (unused by holosoma) |

### SMPLH 52-joint order (holosoma SMPLH_DEMO_JOINTS)

```
 0: Pelvis        1: L_Hip       2: L_Knee      3: L_Ankle     4: L_Toe
 5: R_Hip         6: R_Knee      7: R_Ankle     8: R_Toe
 9: Torso        10: Spine      11: Chest      12: Neck       13: Head
14: L_Thorax     15: L_Shoulder 16: L_Elbow    17: L_Wrist
18-32: Left hand fingers  (Index / Middle / Pinky / Ring / Thumb, 3 joints each)
33: R_Thorax     34: R_Shoulder 35: R_Elbow    36: R_Wrist
37-51: Right hand fingers (Index / Middle / Pinky / Ring / Thumb, 3 joints each)
```

---

## Installation

```bash
git clone https://github.com/Alexyuren/holosomaDateConvert
cd holosomaDateConvert
pip install -r requirements.txt
```

### SMPLH Model Files

SMPLH model files (`.pkl`) are required. Register and download from [MANO](https://mano.is.tue.mpg.de/).

Place them in the following structure:

```
/your/model/path/
└── smplh/
    ├── SMPLH_MALE.pkl
    └── SMPLH_FEMALE.pkl
```

---

## Usage

```bash
python convert.py \
    --input      /path/to/smpl_results.pt \
    --output     /path/to/output.pt \
    --model_path /path/to/smplx \
    --gender     male
```

### Arguments

| Argument | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `--input` | ✓ | — | Path to input SMPL `.pt` file |
| `--output` | ✓ | — | Path to save converted `.pt` file |
| `--model_path` | ✓ | — | Directory containing the `smplh/` folder |
| `--gender` | | `male` | `male` / `female` / `neutral` |
| `--batch_size` | | `512` | Frames per FK batch (reduce if OOM) |

### Input File Format

The input `.pt` file must be a dict with the following keys under `smpl_params_global`:

```python
{
    "smpl_params_global": {
        "body_pose":     torch.Tensor,  # (T, 63)
        "global_orient": torch.Tensor,  # (T, 3)
        "betas":         torch.Tensor,  # (T, 10)
        "transl":        torch.Tensor,  # (T, 3)
    }
}
```

---

## Use in Holosoma

Place the output file in your holosoma data directory and run retargeting:

```bash
# Single sequence
python examples/robot_retarget.py \
    --data_path /path/to/data_dir \
    --task-name output \
    --data_format smplh \
    --task-type robot_only \
    --retargeter.visualize

# Batch processing
python examples/parallel_robot_retarget.py \
    --data-dir /path/to/data_dir \
    --task-type robot_only \
    --data_format smplh \
    --save_dir ./results
```

---

## Related Projects

- [Holosoma](https://github.com/amazon-far/holosoma) — Humanoid robot motion retargeting framework (Amazon)
- [smplx](https://github.com/vchoutas/smplx) — Python library for SMPL-family models
- [SMPL](https://smpl.is.tue.mpg.de/) — SMPL body model (MPI)
- [MANO](https://mano.is.tue.mpg.de/) — SMPLH model download
