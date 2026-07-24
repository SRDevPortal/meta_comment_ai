# Step-by-Step Assignment Configuration Guide

**System:** `https://sriaas.butest.tech`  
**Objective:** Prevent `New` leads from being assigned by rules intended only for `Fresh` leads.

> Complete the steps in order. Do not bulk-update affected leads until the rule changes and queue cleanup are finished.

## Step 1: Back up the current configuration

1. Sign in with an account authorized to manage assignment rules.
2. Open the New Assignment System configuration.
3. Export the assignment rules, or take screenshots of every field in each rule that will be changed.
4. Export the affected assignment logs.
5. Record all pending and retrying assignment queue entries.
6. Store the exports and screenshots with the change record.

**Checkpoint:** Current rules, logs, and queues have been captured.

## Step 2: Temporarily disable the affected rules

1. Open `Parkinson Domestic Assigment Lead`.
2. Turn off **Enabled**.
3. Save the rule.
4. Open `Vericocele Assigning Rule`.
5. Turn off **Enabled** if the Vericocele records will also be corrected.
6. Save the rule.
7. Check the assignment logs and confirm that these rules are no longer creating new assignments.

**Checkpoint:** The affected rules are disabled.

## Step 3: Correct the Parkinson Domestic rule

1. Open `Parkinson Domestic Assigment Lead`.
2. Keep the rule disabled while editing.
3. Confirm **Pipeline** is `Parkinson Domestic`.
4. Set **Status** to `Fresh`.
5. Set **Only If Unassigned** to **Yes**.
6. Keep **Strategy** as `Balanced Load`.
7. Do not change the existing priority, users, or weights.
8. Save the rule.
9. Reopen it and verify that **Status** displays `Fresh` and is not blank.

**Checkpoint:** Parkinson Domestic explicitly matches only unassigned Fresh leads.

## Step 4: Correct the Vericocele rule

1. Open `Vericocele Assigning Rule`.
2. Keep the rule disabled while editing.
3. Keep its existing pipeline.
4. Set **Status** to `Fresh`.
5. Set **Only If Unassigned** to **Yes**, unless reassignment is an approved requirement.
6. Do not change its strategy, priority, users, or weights.
7. Save the rule.
8. Reopen it and verify that **Status** displays `Fresh`.

**Checkpoint:** The Vericocele rule has an explicit status.

## Step 5: Review all remaining enabled rules

For every assignment rule:

1. Open the rule.
2. Check whether **Status** is blank.
3. If the rule should assign only Fresh leads, set **Status** to `Fresh`.
4. If it should assign another status, select that status explicitly and record the approval.
5. Do not leave the status blank.
6. Set **Only If Unassigned** to **Yes** unless owner replacement is specifically required and approved.
7. Save the rule.
8. Reopen it and confirm the saved values.
9. Record the old and new values in the change record.

**Checkpoint:** No enabled rule has a blank status.

## Step 6: Verify global settings

Open the global assignment settings and confirm:

1. **Assignment system** is enabled.
2. **Assign new leads automatically** is enabled.
3. **Assign immediately on creation** is enabled.
4. **Fresh lead status** is `Fresh`.
5. **Reassign leads when watched fields change** is disabled.
6. Check **Assign leads by status change**:
   - Keep it enabled only when approved status-based workflows require it.
   - Ensure every eligible destination status has an explicit rule or mapping.
7. Confirm there is no assignment mapping for `New`.
8. Do not change the existing `Unqualified Leads → unqualified@sriaas.com` mapping.
9. Save only if a correction was required.

**Checkpoint:** `New` is not configured as an automatically assigned status.

## Step 7: Clean up old queue entries

1. Open the assignment queue administration page.
2. Find pending and retrying entries created before the rule correction.
3. Filter them using:
   - affected lead IDs;
   - `Parkinson Domestic Assigment Lead`;
   - `Vericocele Assigning Rule`; and
   - the affected pipelines.
4. Export or screenshot the filtered entries.
5. Confirm that each selected entry belongs to the incorrect assignment activity.
6. Cancel the affected entries using the supported administration action.
7. Do not cancel unrelated queue work.
8. Refresh the queue and confirm that cancelled entries do not return to pending or retrying status.
9. Record the queue IDs and cancellation time.

**Checkpoint:** Work created under the incorrect configuration cannot run later.

## Step 8: Prepare test leads

1. Use dedicated test records, not active customer leads.
2. Prepare at least these test cases:
   - an unassigned `Fresh` lead in `Parkinson Domestic`;
   - an unassigned lead that can be changed from `Fresh` to `New`;
   - an unassigned `New` lead for a non-status update;
   - a manually assigned `New` lead; and
   - a `Fresh` lead outside the Parkinson Domestic pipeline.
3. Record every test lead ID.

**Checkpoint:** Test data is ready and traceable.

## Step 9: Test the Parkinson Domestic rule

1. Re-enable `Parkinson Domestic Assigment Lead`.
2. Save the rule.
3. Create or submit the unassigned `Fresh` Parkinson Domestic test lead.
4. Confirm that it is assigned by the rule.
5. Change the second test lead from `Fresh` to `New`.
6. Confirm that it remains unassigned.
7. Update a non-status field on the unassigned `New` test lead.
8. Confirm that it remains unassigned.
9. Update the manually assigned `New` test lead.
10. Confirm that its manual owner does not change.
11. Process the `Fresh` lead outside Parkinson Domestic.
12. Confirm that this rule does not assign it.
13. Review the assignment logs and queue after every test.

**Stop condition:** If any `New` lead is assigned, disable the rule immediately, preserve the logs, cancel its new queue entries, and escalate for a code correction.

**Checkpoint:** Fresh assignment works and New leads remain untouched.

## Step 10: Test and enable the other corrected rules

For each corrected rule:

1. Keep all other untested rules disabled where practical.
2. Enable one corrected rule.
3. Test an eligible unassigned `Fresh` lead.
4. Test a lead changed from `Fresh` to `New`.
5. Test a manually assigned `New` lead.
6. Review its assignment logs and queue entries.
7. Leave the rule enabled only if every test passes.
8. Record the test lead IDs and results.

**Checkpoint:** Each rule was validated separately.

## Step 11: Monitor a controlled batch

1. Process only 5–10 Fresh leads initially.
2. Confirm that eligible Fresh leads are distributed normally.
3. Confirm that no New lead is assigned or reassigned.
4. Monitor the logs and queue for at least one complete processing cycle.
5. Check that cancelled retry entries do not return.
6. If results are correct, resume normal processing.

**Checkpoint:** Correct behavior is confirmed under controlled production activity.

## Step 12: Correct previously affected assignments

1. Export assignment actions associated with the incident.
2. Deduplicate the list by lead ID.
3. Identify owners added by the affected automatic rules.
4. Check whether each lead received a later legitimate manual assignment.
5. Preserve every legitimate manual owner.
6. Clear only owners created by the incorrect automatic assignment.
7. Remove related ToDos or sharing entries only when:
   - they were created by the incorrect assignment; and
   - their removal has been approved.
8. Test the recovery process on 5–10 leads.
9. Validate their status, owner, logs, ToDos, and sharing.
10. Correct the remaining affected records only after the sample passes.

**Checkpoint:** Incorrect automatic owners are removed without affecting legitimate work.

## Step 13: Complete the change record

Record:

- implementation start and end times;
- rules changed;
- old and new configuration values;
- queue entries cancelled;
- test lead IDs;
- test results;
- affected assignments corrected;
- exceptions and approvals;
- implementer and validator names; and
- final monitoring result.

Obtain sign-off from the CRM administrator and business owner.

## Final verification checklist

- [ ] Every enabled assignment rule has an explicit status.
- [ ] Fresh-only rules use `Status = Fresh`.
- [ ] `Only If Unassigned` is enabled except for approved exceptions.
- [ ] No explicit automatic-assignment rule or mapping targets `New`.
- [ ] Old affected queue entries are cancelled.
- [ ] A new Fresh lead is assigned correctly.
- [ ] A lead changed from Fresh to New remains unassigned.
- [ ] Updating a New lead does not assign it.
- [ ] A manually assigned New lead keeps its owner.
- [ ] Controlled-batch monitoring shows no incorrect assignments.
- [ ] Recovery preserves all legitimate manual assignments.
- [ ] Evidence and approvals are attached to the change record.
