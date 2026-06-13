# AMP Auto Finish Summary (2026-05-01 05:44:33)

## Root
- root: `amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637`
- dashboard: `http://127.0.0.1:8789/?root=amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637`
- status: `completed`
- current_stage: `completed`

## Final Metrics
- overall_long_samples: `1000013824`
- long_target_samples: `1000000000`
- Test_Return: `428.61610412597656`
- Train_Return: `430.1156311035156`
- Disc_Reward_Mean: `0.2771313488483429`
- Disc_Agent_Acc / Disc_Demo_Acc: `0.992993175983429` / `1.0`

## Artifacts
- model_file: `/root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/long_train/model.pt`
- arg_file: `args/amp_location_humanoid_sword_shield_args.txt`
- best_by_case: `/root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/best_by_case.tsv`
- infer_viz_index: `/root/Project/MimicKit/output/img/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/infer_viz_index.tsv`
- render_meta_count: `1`
- mp4_count: `1`

## Auto Finish Stages
- watching: `completed` rc=`0` log=`` notes=`detected long_train completion`
- triggered: `completed` rc=`0` log=`` notes=`auto-finish pipeline starting`
- build_best_by_case: `completed` rc=`0` log=`/root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/session_logs/autofinish_build_best_by_case.attempt01.log` notes=`attempt=1`
- post_train_test: `completed` rc=`0` log=`/root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/session_logs/autofinish_post_train_test.attempt01.log` notes=`attempt=1`
- post_train_visualize: `completed` rc=`0` log=`/root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/session_logs/autofinish_post_train_visualize.attempt01.log` notes=`attempt=1`
- post_train_render: `completed` rc=`0` log=`/root/Project/MimicKit/output/train/amp_WalkBrain_dual_newton_hiutil_e1024_20260430_220637/session_logs/autofinish_post_train_render.attempt01.log` notes=`attempt=1 mp4_count=1`
- completed: `completed` rc=`None` log=`` notes=`all auto-finish stages completed`

## Warnings
- discriminator: 判别器失衡
- render: render ready

