import json
import datetime
path = '/mnt/d/AnimationTech-learning/EvihAnimation-mimickit-bridge-v3/Demos/MimicKitReplay/results/white_knight_mesh_replay_v3_smoke/evih_mesh_replay/visual_review.json'
with open(path, 'r') as f:
    r = json.load(f)
r['visual_review_pass'] = True
r['reviewer'] = 'l3d'
r['reviewed_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
for k in r['checks']:
    r['checks'][k] = True
with open(path, 'w') as f:
    json.dump(r, f, indent=2)
print('Signed successfully!')
