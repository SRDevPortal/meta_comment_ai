# Meta Comment AI

Frappe app for collecting Facebook and Instagram comments, drafting AI-safe medical replies, capturing phone leads in CRM, and auditing every action.

## Install / Build

Fresh install:

```bash
cd /home/frappe/frappe-bench
bench get-app https://github.com/SRDevPortal/meta_comment_ai.git --branch develop
bench --site your-site-name install-app meta_comment_ai
```

This app includes a small `postinstall` hook that registers `meta_comment_ai` in `sites/apps.txt` before Bench starts asset build. This prevents Frappe esbuild from failing with `paths[0] ... Received undefined` during `bench get-app`.

If you are recovering an older checkout, register the app once before building:

```bash
grep -qxF meta_comment_ai sites/apps.txt || echo meta_comment_ai >> sites/apps.txt
bench setup requirements
bench build --app meta_comment_ai
```
