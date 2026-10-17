#!/bin/bash
# Re-render the lute .vd from Lute_poses.blend, pose by pose (actions of one pose together), into one folder; the renderer adds the runs up into one clothing.vd.
# usage: ./render_lute.sh OUT_DIR      (needs bpy 4.2 in the python on PATH, run from the repo root: model/example_clothing/lute/render_lute.sh /tmp/lute)
set -e
OUT=${1:-/tmp/lute_render}; BLEND=model/example_clothing/lute/Lute_poses.blend; TMP=$(mktemp -d)
COMMON=("LAYER='clothing'" "CANVAS=(256,256)" "ANCHOR=(128,192)" "OWN_PARTS_NEVER_HIDE=False" "TORSO_HIDE_MARGIN=0.005" "HOLDOUT_MARGIN=0.003")
run() {   # pose, python list of action names, extra settings...
  python pipeline/lute_select_pose.py $BLEND "Lute_$1" $TMP/$1.blend > /dev/null
  p=$1; a=$2; shift 2
  python pipeline/run_render_headless.py $TMP/$p.blend "$OUT" "ONLY=$a" "${COMMON[@]}" "$@"
}
HANDS=("HAND_OVER=0.12" "HAND_OVER_GROW=1" "HAND_OVER_SIDE='.R'")
run carry "['00_walk_unarmed','01_walk_armed','02_run_unarmed','03_run_armed']"
run stand "['04_stand']" "HAND_OVER=0.3" "HAND_OVER_GROW=2" "HAND_OVER_SIDE='.R'"
run fid1 "['05_fidget_1']" "${HANDS[@]}"
run fid2 "['06_fidget_2']" "${HANDS[@]}"
run h07 "['07_combat_idle_1h','20_get_hit']"
run h15 "['15_combat_advance']"
run sp "['16_spell_directed','17_spell_area']"
run d21 "['21_die_forward']"
run d22 "['22_die_backward']" "HAND_OVER=0.2" "HAND_OVER_GROW=1" "HAND_OVER_PARTS=('hand','forearm','upper_arm')"
run m23 "['23_mounted_walk']" "HORSE_HOLDOUT=False"
run m24 "['24_mounted_run']" "HORSE_HOLDOUT=False" "HAND_OVER=0.2" "HAND_OVER_GROW=1" "HAND_OVER_SIDE='.R'" "HAND_OVER_PARTS=('hand','forearm','upper_arm')"
run m25 "['25_mounted_stand']" "HORSE_HOLDOUT=False" "HAND_OVER=0.3" "HAND_OVER_GROW=2" "HAND_OVER_SIDE='.R'"
run h26 "['26_mounted_attack_1h']"
run h30 "['30_block']"
run h33 "['33_salute']"
run eat "['34_eat']"
run handrigid "['08_combat_idle_2h','09_attack_1h_slash','10_attack_1h_pierce','11_attack_1h_bash','12_attack_2h_bash','13_attack_2h_slash','14_attack_2h_pierce','18_attack_bow','19_attack_crossbow','27_mounted_attack_bow','28_mounted_attack_crossbow','29_mounted_attack_2h','31_punch','32_bow']"
echo "wrote $OUT/clothing.vd"
