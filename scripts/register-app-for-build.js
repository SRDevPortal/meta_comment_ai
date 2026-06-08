const fs = require("fs");
const path = require("path");

const appName = "meta_comment_ai";
const benchRoot = path.resolve(__dirname, "..", "..", "..");
const appsTxtPath = path.join(benchRoot, "sites", "apps.txt");

if (fs.existsSync(appsTxtPath)) {
	const content = fs.readFileSync(appsTxtPath, "utf8");
	const apps = content.split(/\r?\n/).filter(Boolean);

	if (!apps.includes(appName)) {
		const newline = content && !content.endsWith("\n") ? "\n" : "";
		fs.appendFileSync(appsTxtPath, `${newline}${appName}\n`);
		console.log(`Registered ${appName} in sites/apps.txt for asset build`);
	}
}
