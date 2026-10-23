# Campaign Sources

These Markdown files are the human-readable source of truth for campaign rules. Runtime YAML files in [`backend/campaigns/`](../../../backend/campaigns/) are the machine-readable copies used by the analysis pipeline.

When a campaign changes:

1. Update the Markdown source first.
2. Update the matching YAML version and criteria.
3. Keep the same campaign ID unless this is a genuinely new campaign.
4. Record the change in [`documentation/operations/WORKLOG.md`](../../operations/WORKLOG.md).

Campaigns target the businesses Prime Ad sells to. The **opener** is the appointment setter; the **closer** runs the meeting.

The earlier `cgm_healthcare.yaml` scaffold remains only for historical references and is inactive. New meetings should use `cgm_patient_acquisition`.
