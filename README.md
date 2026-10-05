# Meta Comment AI

Frappe app for collecting Facebook and Instagram comments, drafting AI-safe medical replies, capturing phone leads in CRM, and auditing every action.

## Install / Build

Fresh install:

```bash
cd /home/frappe/frappe-bench
bench get-app https://github.com/SRDevPortal/meta_comment_ai.git --branch develop
bench --site your-site-name install-app meta_comment_ai
```

## Customer number privacy

When Customer Number Privacy is enabled, the Meta Comment Inbox masks captured
phone fields and phone-like text for restricted users. Raw webhook events and AI
request/response payloads stay available to internal processing and users with
full-number visibility. Restricted users cannot open, print, export, or search
raw Meta Comment and Meta Comment Action records by phone number. Provider calls
and CRM Lead creation continue to use the original values.
