# SMPL → Holosoma Data Converter

将标准 **SMPL 参数数据**（`body_pose` + `global_orient` + `betas` + `transl`）通过正向运动学转换为 [Holosoma Motion Retargeting](https://github.com/amazon-far/holosoma) 所需的 **SMPLH 52关节全局3D位置**格式，用于后续人形机器人动作迁移（retargeting）。

---

## 背景

[Holosoma](https://github.com/amazon-far/holosoma) 是亚马逊开源的人形机器人运动迁移框架，支持将人类运动数据迁移到 Unitree G1 等人形机器人上。其 retargeting 模块要求输入数据为 **OMOMO_new / InterMimic 格式**，即包含 **SMPLH 52个关节全局3D位置** 的 `.pt` 文件。

本工具的输入为标准 **SMPL 参数**（24关节，包含 `body_pose`、`global_orient`、`betas`、`transl`），可来自任意 SMPL 兼容系统（如 HMR4D、CLIFF、4D-Humans 等）。

输入与 Holosoma 要求之间存在以下差异，需要转换：

| 项目 | SMPL 输入 | Holosoma 要求 |
|------|-----------|--------------|
| 关节数 | 24（SMPL） | 52（SMPLH） |
| 数据形式 | 旋转参数（axis-angle） | 全局3D关节位置（米） |
| 坐标系 | Y-up | Z-up |
| 关节顺序 | smplx 标准顺序 | holosoma SMPLH_DEMO_JOINTS 顺序 |
| 文件格式 | dict（含多个字段） | `[T, 591]` float32 张量 |

本工具完成上述所有转换，输出可直接用于 Holosoma retargeting pipeline 的 `.pt` 文件。

---

## 转换流程

```
HMR4D 输出 (smpl_params_global)
    │
    │  body_pose (T,63) + global_orient (T,3) + betas (T,10) + transl (T,3)
    ▼
SMPLH 正向运动学 (smplx 库)
    │
    │  输出 52 个关节的全局3D坐标 (T, 52, 3)
    ▼
关节顺序重排
    │
    │  smplx 标准顺序 → holosoma SMPLH_DEMO_JOINTS 顺序
    ▼
坐标系转换
    │
    │  Y-up (HMR4D) → Z-up (holosoma): (x,y,z) → (z,x,y)
    ▼
打包为 [T, 591] 张量
    │
    │  列 162-317: 关节位置（核心数据）
    │  其余列: 零填充或 identity 物体位姿
    ▼
输出 hmr4d_holosoma.pt  ← 可直接用于 holosoma retargeting
```

---

## 输出格式说明

输出为 `[T, 591]` float32 张量，与 Holosoma `demo_data/OMOMO_new` 数据集格式完全一致：

| 列范围 | 维度 | 内容 |
|--------|------|------|
| 0 – 161 | 162 | 全零（holosoma 不使用） |
| **162 – 317** | **156 = 52×3** | **52个SMPLH关节全局3D坐标，Z-up，单位米** |
| 318 – 324 | 7 | 物体位姿 `[x,y,z,qx,qy,qz,qw]`（无物体时为 identity） |
| 325 – 590 | 266 | 全零（holosoma 不使用） |

### SMPLH 52个关节顺序（holosoma SMPLH_DEMO_JOINTS）

```
 0: Pelvis        1: L_Hip       2: L_Knee      3: L_Ankle     4: L_Toe
 5: R_Hip         6: R_Knee      7: R_Ankle     8: R_Toe
 9: Torso        10: Spine      11: Chest      12: Neck       13: Head
14: L_Thorax     15: L_Shoulder 16: L_Elbow    17: L_Wrist
18-32: 左手指 (Index/Middle/Pinky/Ring/Thumb 各3节)
33: R_Thorax     34: R_Shoulder 35: R_Elbow    36: R_Wrist
37-51: 右手指 (Index/Middle/Pinky/Ring/Thumb 各3节)
```

---

## 安装

```bash
git clone https://github.com/Alexyuren/holosomaDateConvert
cd holosomaDateConvert
pip install -r requirements.txt
```

### 依赖

- `torch >= 2.0.0`
- `smplx >= 0.1.28`
- `numpy >= 1.21.0`

### SMPLH 模型文件

需要 SMPLH 模型文件（`.pkl`），请前往 [MANO 官网](https://mano.is.tue.mpg.de/) 注册下载。

下载后按如下目录结构放置：

```
/your/model/path/
└── smplh/
    ├── SMPLH_MALE.pkl
    └── SMPLH_FEMALE.pkl
```

---

## 使用方法

```bash
python convert.py \
    --input     /path/to/hmr4d_results.pt \
    --output    /path/to/hmr4d_holosoma.pt \
    --model_path /path/to/smplx \
    --gender    male
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `--input` | ✓ | — | HMR4D 输出文件路径（`hmr4d_results.pt`） |
| `--output` | ✓ | — | 转换后输出文件路径 |
| `--model_path` | ✓ | — | 包含 `smplh/` 文件夹的目录路径 |
| `--gender` | | `male` | `male` / `female` / `neutral` |
| `--batch_size` | | `512` | 每批处理帧数，内存不足可调小 |

---

## 在 Holosoma 中使用

转换完成后，将输出文件放入 holosoma 的数据目录，即可运行 retargeting：

```bash
# 单序列 retargeting
python examples/robot_retarget.py \
    --data_path /path/to/data_dir \
    --task-name hmr4d_holosoma \
    --data_format smplh \
    --task-type robot_only \
    --retargeter.visualize

# 批量处理
python examples/parallel_robot_retarget.py \
    --data-dir /path/to/data_dir \
    --task-type robot_only \
    --data_format smplh \
    --save_dir ./results
```

---

## 相关项目

- [Holosoma](https://github.com/amazon-far/holosoma) — 人形机器人运动迁移框架（Amazon）
- [smplx](https://github.com/vchoutas/smplx) — SMPL 系列模型 Python 库
- [SMPL](https://smpl.is.tue.mpg.de/) — SMPL 人体模型（MPI）
- [MANO](https://mano.is.tue.mpg.de/) — SMPLH 模型下载
