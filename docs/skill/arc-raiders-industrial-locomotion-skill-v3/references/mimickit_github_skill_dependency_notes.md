# MimicKit GitHub Skill Dependency Notes

Source branch supplied by the user:

```text
https://github.com/EvihGraphics/MimicKit/tree/feat/ase-prework
```

Relevant source paths:

```text
docs/skill/mimickit-ase-dashboard-skill/SKILL.md
docs/skill/mimickit-render-viz-sequence-skill/SKILL.md
```

Required new sibling path:

```text
docs/skill/mimickit-amp-dashboard-skill/SKILL.md
```

Codex behavior:

1. Read the ASE dashboard skill first.
2. Read the render-viz sequence skill second.
3. Create the AMP dashboard skill as a sibling, not a replacement.
4. Keep the style and operational conventions aligned.
5. Remove or guard ASE-only latent metrics.
6. Pair checkpoint quality decisions with render-viz outputs.
7. Preserve the industrial ARC-like pipeline goal: MimicKit learning -> AI4AnimationPy demo validation -> UE5 production deployment.
