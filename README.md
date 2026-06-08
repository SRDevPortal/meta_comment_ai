# Meta Comment AI

Frappe app for collecting Facebook and Instagram comments, drafting AI-safe medical replies, capturing phone leads in CRM, and auditing every action.

## Install / Build

If `bench build --app meta_comment_ai` fails with `paths[0] ... Received undefined`, ensure the app is registered in `sites/apps.txt` before building:

```bash
cd /home/frappe/frappe-bench
grep -qxF meta_comment_ai sites/apps.txt || echo meta_comment_ai >> sites/apps.txt
bench setup requirements
bench build --app meta_comment_ai
```

For a fresh install, this also works:

```bash
bench get-app https://github.com/SRDevPortal/meta_comment_ai.git --skip-assets
grep -qxF meta_comment_ai sites/apps.txt || echo meta_comment_ai >> sites/apps.txt
bench setup requirements
bench build --app meta_comment_ai
```
