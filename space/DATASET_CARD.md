# Dataset card: synthetic fixture and static replay

The built-in fixture uses deterministic machine-generated scenes and scripted decisions to exercise image, box, review and audit workflows. It is intended for software testing and demonstrations, not model accuracy or population prevalence claims. Artificial omissions are seeded and are not reviewed by people. Synthetic fixture source and generated geometry are licensed under Apache-2.0 with this project.

The replay may also include separately licensed public photos and COCO annotations. Those are not covered by the fixture's code license; per-image attribution, modifications, hashes and license links are in [the public media manifest](ATTRIBUTION.md). The photos do not constitute an independently adjudicated cohort. A replay is recorded inference, and visitor actions do not change the original audit. KITTI and ReChecked inputs are not part of this shareable artifact.
