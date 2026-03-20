# HMR4D → Holosoma Retargeting 数据转换工具

将 HMR4D 输出的 `smpl_params_global` 转换为 holosoma retargeting 所需的 `.pt` 格式。

## 输出格式

生成 `[T, 591]` float32 张量，列布局与 OMOMO_new / InterMimic 数据集一致：

| 列范围 | 维度 | 内容 |
|--------|------|------|
| 0–161 | 162 | 全零（holosoma 不使用） |
| **162–317** | **156** | **52个SMPLH关节全局3D坐标（Z-up，单位米）** |
| 318–324 | 7 | 物体位姿（无物体场景填 identity） |
| 325–590 | 266 | 全零（holosoma 不使用） |

## 安装依赖

```bash
pip install -r requirements.txt
```

## 准备 SMPLH 模型文件

需要 SMPLH 模型文件，目录结构如下：

```
/your/model/path/
└── smplh/
    ├── SMPLH_MALE.pkl
    └── SMPLH_FEMALE.pkl
```

从 https://mano.is.tue.mpg.de/ 下载（需注册）。

## 使用方法

```bash
python convert.py \
    --input  hmr4d_results.pt \
    --output hmr4d_holosoma.pt \
    --model_path /path/to/smplx \
    --gender male
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `--input` | ✓ | — | HMR4D 输出文件路径 |
| `--output` | ✓ | — | 输出文件路径 |
| `--model_path` | ✓ | — | 包含 `smplh/` 文件夹的目录 |
| `--gender` | | male | male / female / neutral |
| `--batch_size` | | 512 | 每批处理帧数，内存不足可调小 |

## 在 holosoma 中使用

```bash
python examples/robot_retarget.py \
    --data_path /path/to/output_dir \
    --task-name hmr4d_holosoma \
    --data_format smplh \
    --task-type robot_only
```

## 技术说明

**两个关键转换：**

1. **关节顺序重排**：smplx 输出顺序 vs holosoma `SMPLH_DEMO_JOINTS` 顺序不同，
   通过 `SMPLX_TO_HOLOSOMA` 映射表对52个关节逐一重排。

2. **坐标系转换**：HMR4D 输出 Y-up，holosoma 期望 Z-up，
   变换规则：`(x, y, z) → (x, z, y)`（交换 Y 和 Z 轴）。
