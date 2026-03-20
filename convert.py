"""
Convert hmr4d_results.pt → holosoma retargeting format (.pt, shape [T, 591])

Usage:
    python convert.py \
        --input  hmr4d_results.pt \
        --output hmr4d_holosoma.pt \
        --model_path /path/to/smplx \
        --gender male \
        --batch_size 512

Column layout (OMOMO_new / InterMimic format):
  cols   0-161  : zeros (not used by holosoma)
  cols 162-317  : 52 SMPLH joint global positions, flattened (52×3=156)
  cols 318-324  : object pose [x,y,z,qx,qy,qz,qw]  — identity (no object)
  cols 325-590  : zeros (not used by holosoma)

Coordinate system:
  Input  (HMR4D smpl_params_global): Y-up  (x=right, y=up,     z=depth)
  Output (holosoma):                 Z-up  (x=right, y=depth,  z=up)
  Transform: (x, y, z) → (x, z, y)

Joint reordering:
  smplx SMPLH joint order  → holosoma SMPLH_DEMO_JOINTS order (52 joints)
"""

import argparse
import torch
import smplx
from pathlib import Path


# ── joint reorder map ────────────────────────────────────────────────────────
# SMPLX_TO_HOLOSOMA[i] = smplx joint index that maps to holosoma position i
#
# smplx order : pelvis(0), l_hip(1), r_hip(2), spine1(3), l_knee(4),
#               r_knee(5), spine2(6), l_ankle(7), r_ankle(8), spine3(9),
#               l_foot(10), r_foot(11), neck(12), l_collar(13), r_collar(14),
#               head(15), l_shoulder(16), r_shoulder(17), l_elbow(18),
#               r_elbow(19), l_wrist(20), r_wrist(21), l_hand(22-36), r_hand(37-51)
#
# holosoma order: Pelvis(0), L_Hip(1), L_Knee(2), L_Ankle(3), L_Toe(4),
#                 R_Hip(5), R_Knee(6), R_Ankle(7), R_Toe(8),
#                 Torso(9), Spine(10), Chest(11), Neck(12), Head(13),
#                 L_Thorax(14), L_Shoulder(15), L_Elbow(16), L_Wrist(17),
#                 L_hand(18-32),
#                 R_Thorax(33), R_Shoulder(34), R_Elbow(35), R_Wrist(36),
#                 R_hand(37-51)
SMPLX_TO_HOLOSOMA = [
     0,  # holosoma[ 0] Pelvis      ← smplx[ 0] pelvis
     1,  # holosoma[ 1] L_Hip       ← smplx[ 1] left_hip
     4,  # holosoma[ 2] L_Knee      ← smplx[ 4] left_knee
     7,  # holosoma[ 3] L_Ankle     ← smplx[ 7] left_ankle
    10,  # holosoma[ 4] L_Toe       ← smplx[10] left_foot
     2,  # holosoma[ 5] R_Hip       ← smplx[ 2] right_hip
     5,  # holosoma[ 6] R_Knee      ← smplx[ 5] right_knee
     8,  # holosoma[ 7] R_Ankle     ← smplx[ 8] right_ankle
    11,  # holosoma[ 8] R_Toe       ← smplx[11] right_foot
     3,  # holosoma[ 9] Torso       ← smplx[ 3] spine1
     6,  # holosoma[10] Spine       ← smplx[ 6] spine2
     9,  # holosoma[11] Chest       ← smplx[ 9] spine3
    12,  # holosoma[12] Neck        ← smplx[12] neck
    15,  # holosoma[13] Head        ← smplx[15] head
    13,  # holosoma[14] L_Thorax    ← smplx[13] left_collar
    16,  # holosoma[15] L_Shoulder  ← smplx[16] left_shoulder
    18,  # holosoma[16] L_Elbow     ← smplx[18] left_elbow
    20,  # holosoma[17] L_Wrist     ← smplx[20] left_wrist
    22,  # holosoma[18] L_Index1    ← smplx[22] left_index1
    23,  # holosoma[19] L_Index2    ← smplx[23] left_index2
    24,  # holosoma[20] L_Index3    ← smplx[24] left_index3
    25,  # holosoma[21] L_Middle1   ← smplx[25] left_middle1
    26,  # holosoma[22] L_Middle2   ← smplx[26] left_middle2
    27,  # holosoma[23] L_Middle3   ← smplx[27] left_middle3
    28,  # holosoma[24] L_Pinky1    ← smplx[28] left_pinky1
    29,  # holosoma[25] L_Pinky2    ← smplx[29] left_pinky2
    30,  # holosoma[26] L_Pinky3    ← smplx[30] left_pinky3
    31,  # holosoma[27] L_Ring1     ← smplx[31] left_ring1
    32,  # holosoma[28] L_Ring2     ← smplx[32] left_ring2
    33,  # holosoma[29] L_Ring3     ← smplx[33] left_ring3
    34,  # holosoma[30] L_Thumb1    ← smplx[34] left_thumb1
    35,  # holosoma[31] L_Thumb2    ← smplx[35] left_thumb2
    36,  # holosoma[32] L_Thumb3    ← smplx[36] left_thumb3
    14,  # holosoma[33] R_Thorax    ← smplx[14] right_collar
    17,  # holosoma[34] R_Shoulder  ← smplx[17] right_shoulder
    19,  # holosoma[35] R_Elbow     ← smplx[19] right_elbow
    21,  # holosoma[36] R_Wrist     ← smplx[21] right_wrist
    37,  # holosoma[37] R_Index1    ← smplx[37] right_index1
    38,  # holosoma[38] R_Index2    ← smplx[38] right_index2
    39,  # holosoma[39] R_Index3    ← smplx[39] right_index3
    40,  # holosoma[40] R_Middle1   ← smplx[40] right_middle1
    41,  # holosoma[41] R_Middle2   ← smplx[41] right_middle2
    42,  # holosoma[42] R_Middle3   ← smplx[42] right_middle3
    43,  # holosoma[43] R_Pinky1    ← smplx[43] right_pinky1
    44,  # holosoma[44] R_Pinky2    ← smplx[44] right_pinky2
    45,  # holosoma[45] R_Pinky3    ← smplx[45] right_pinky3
    46,  # holosoma[46] R_Ring1     ← smplx[46] right_ring1
    47,  # holosoma[47] R_Ring2     ← smplx[47] right_ring2
    48,  # holosoma[48] R_Ring3     ← smplx[48] right_ring3
    49,  # holosoma[49] R_Thumb1    ← smplx[49] right_thumb1
    50,  # holosoma[50] R_Thumb2    ← smplx[50] right_thumb2
    51,  # holosoma[51] R_Thumb3    ← smplx[51] right_thumb3
]


def convert(input_path, output_path, model_path, gender, batch_size):
    # ── load hmr4d data ───────────────────────────────────────────────────────
    print(f"Loading {input_path} ...")
    hmr4d = torch.load(input_path, map_location="cpu", weights_only=False)

    smpl_global  = hmr4d["smpl_params_global"]
    body_pose    = smpl_global["body_pose"].float()      # (T, 63)
    global_orient= smpl_global["global_orient"].float()  # (T,  3)
    betas        = smpl_global["betas"].float()          # (T, 10)
    transl       = smpl_global["transl"].float()         # (T,  3)
    T = body_pose.shape[0]
    print(f"  Total frames: {T}")

    # ── build SMPLH model ─────────────────────────────────────────────────────
    print("Building SMPLH model ...")
    smplh_model = smplx.create(
        model_path    = str(model_path),
        model_type    = "smplh",
        gender        = gender,
        use_pca       = False,
        flat_hand_mean= True,
        batch_size    = batch_size,
    )
    smplh_model.eval()

    # ── forward kinematics in batches ─────────────────────────────────────────
    print("Running SMPLH forward kinematics ...")
    all_joints = []

    with torch.no_grad():
        for start in range(0, T, batch_size):
            end = min(start + batch_size, T)
            n   = end - start
            pad = batch_size - n

            bp = torch.cat([body_pose[start:end],     torch.zeros(pad, 63)], dim=0)
            go = torch.cat([global_orient[start:end], torch.zeros(pad,  3)], dim=0)
            bt = torch.cat([betas[start:end],         torch.zeros(pad, 10)], dim=0)
            tr = torch.cat([transl[start:end],        torch.zeros(pad,  3)], dim=0)

            out = smplh_model(global_orient=go, body_pose=bp, betas=bt, transl=tr)

            # Step 1: take first 52 joints, reorder to holosoma joint convention
            joints_smplx     = out.joints[:n, :52, :]
            joints_reordered = joints_smplx[:, SMPLX_TO_HOLOSOMA, :]

            # Step 2: coordinate transform (verified correct — model stands upright)
            # (x, y, z) → (z, x, y)
            joints_batch = torch.stack([
                joints_reordered[:, :, 2],  # new axis 0 = old z (depth)
                joints_reordered[:, :, 0],  # new axis 1 = old x (lateral)
                joints_reordered[:, :, 1],  # new axis 2 = old y (height)
            ], dim=-1)

            all_joints.append(joints_batch)
            print(f"  frames {start:6d} – {end:6d} / {T}")

    all_joints = torch.cat(all_joints, dim=0)  # (T, 52, 3)

    # ── pack into [T, 591] ────────────────────────────────────────────────────
    print("Packing into [T, 591] format ...")
    result = torch.zeros(T, 591, dtype=torch.float32)

    result[:, 162:318] = all_joints.reshape(T, 156)           # joint positions
    result[:, 318:325] = torch.tensor(                        # identity object pose
        [0., 0., 0., 0., 0., 0., 1.]).expand(T, -1)

    torch.save(result, output_path)
    print(f"\nSaved → {output_path}")
    print(f"Shape : {result.shape}  dtype: {result.dtype}")

    # ── sanity check ─────────────────────────────────────────────────────────
    j = result[:, 162:318].reshape(T, 52, 3)
    print(f"Z range (height) : {j[:,:,2].min():.3f} ~ {j[:,:,2].max():.3f} m")
    print(f"X range (lateral): {j[:,:,0].min():.3f} ~ {j[:,:,0].max():.3f} m")
    print("Done!")


def main():
    parser = argparse.ArgumentParser(description="Convert HMR4D output → holosoma retargeting format")
    parser.add_argument("--input",      type=str, required=True,  help="Path to hmr4d_results.pt")
    parser.add_argument("--output",     type=str, required=True,  help="Path to save output .pt")
    parser.add_argument("--model_path", type=str, required=True,  help="Directory containing smplh/ folder (with SMPLH_MALE.pkl or SMPLH_FEMALE.pkl)")
    parser.add_argument("--gender",     type=str, default="male", choices=["male", "female", "neutral"], help="Gender for SMPLH model (default: male)")
    parser.add_argument("--batch_size", type=int, default=512,    help="Frames per FK batch (default: 512)")
    args = parser.parse_args()

    convert(
        input_path  = args.input,
        output_path = args.output,
        model_path  = Path(args.model_path),
        gender      = args.gender,
        batch_size  = args.batch_size,
    )


if __name__ == "__main__":
    main()
