frappe.pages["meta-comment-inbox"].on_page_load = function(wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Meta Comment Inbox",
        single_column: true,
    });

    let sources = [];
    let selectedSource = null;
    let selectedComment = null;
    const stateKey = "meta_comment_inbox_state";
    let savedState = loadSavedState();

    page.add_inner_button(__("Social Accounts"), () => frappe.set_route("List", "Meta Social Account"));
    page.add_inner_button(__("Settings"), () => frappe.set_route("Form", "Meta Comment AI Settings"));

    page.main.html(`
        <style>
            .mca-shell { width: 100%; max-width: 100%; height: calc(100vh - 126px); border: 1px solid var(--border-color); display: grid; grid-template-columns: minmax(0, 1fr) 420px; overflow: hidden; background: var(--bg-color); }
            .mca-main { min-width: 0; overflow: hidden; border-right: 1px solid var(--border-color); display: flex; flex-direction: column; }
            .mca-side { min-width: 0; overflow: hidden; display: flex; flex-direction: column; background: var(--card-bg); }
            .mca-toolbar { padding: 12px; border-bottom: 1px solid var(--border-color); display: grid; grid-template-columns: minmax(170px, 220px) minmax(170px, 220px) minmax(120px, 145px) minmax(145px, 170px) minmax(180px, 1fr) auto; gap: 8px; align-items: center; }
            .mca-feed { padding: 14px; overflow: auto; }
            .mca-card { border: 1px solid var(--border-color); border-radius: 6px; background: var(--card-bg); margin-bottom: 12px; display: grid; grid-template-columns: 180px minmax(0, 1fr); overflow: hidden; }
            .mca-card-media { background: var(--control-bg); min-height: 180px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
            .mca-card-media img { width: 100%; height: 100%; object-fit: cover; display: block; }
            .mca-card-body { padding: 12px 14px; min-width: 0; }
            .mca-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
            .mca-card-title { font-weight: 700; font-size: 15px; overflow-wrap: anywhere; }
            .mca-caption { color: var(--text-color); white-space: pre-wrap; overflow-wrap: anywhere; max-height: 142px; overflow: auto; padding-right: 4px; }
            .mca-meta { margin-top: 8px; color: var(--text-muted); font-size: 12px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
            .mca-actions { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
            .mca-counts { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
            .mca-count { min-width: 76px; padding: 7px 9px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-color); }
            .mca-count strong { display: block; color: var(--heading-color); font-size: 15px; line-height: 1.1; }
            .mca-count span { color: var(--text-muted); font-size: 11px; }
            .mca-badge { display: inline-flex; align-items: center; min-height: 20px; padding: 1px 7px; border-radius: 4px; background: var(--control-bg); color: var(--text-muted); font-size: 11px; font-weight: 700; }
            .mca-badge.instagram { color: #b83280; background: #fff0f7; }
            .mca-badge.facebook { color: #1264a3; background: #eef6ff; }
            .mca-side-head { padding: 12px 14px; border-bottom: 1px solid var(--border-color); }
            .mca-side-title { font-weight: 700; font-size: 15px; overflow-wrap: anywhere; }
            .mca-side-subtitle { color: var(--text-muted); font-size: 12px; margin-top: 4px; }
            .mca-comment-tools { padding: 10px 14px; border-bottom: 1px solid var(--border-color); display: grid; gap: 8px; }
            .mca-comment-list { overflow: auto; flex: 1 1 auto; min-height: 160px; }
            .mca-comment-row { padding: 12px 14px; border-bottom: 1px solid var(--border-color); cursor: pointer; }
            .mca-comment-row:hover, .mca-comment-row.active { background: var(--fg-hover-color); }
            .mca-comment-head { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 5px; }
            .mca-comment-user { font-weight: 700; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
            .mca-comment-status { color: var(--text-muted); font-size: 11px; white-space: nowrap; }
            .mca-comment-text { font-size: 13px; white-space: pre-wrap; overflow-wrap: anywhere; }
            .mca-detail-panel { max-height: 42%; overflow: auto; border-top: 1px solid var(--border-color); padding: 14px; background: var(--bg-color); }
            .mca-detail-title { font-weight: 700; margin-bottom: 6px; }
            .mca-history-row { border-top: 1px solid var(--border-color); padding: 8px 0; font-size: 12px; }
            .mca-empty { color: var(--text-muted); padding: 34px 18px; text-align: center; }
            @media (max-width: 1100px) { .mca-shell { height: auto; min-height: calc(100vh - 126px); grid-template-columns: minmax(0, 1fr); } .mca-main { border-right: 0; } .mca-side { min-height: 560px; } }
            @media (max-width: 760px) { .mca-toolbar { grid-template-columns: 1fr; } .mca-card { grid-template-columns: 1fr; } .mca-card-media { height: 220px; } }
        </style>
        <div class="mca-shell">
            <section class="mca-main">
                <div class="mca-toolbar">
                    <select class="form-control input-sm" id="mca-account"><option value="">All Master Accounts</option></select>
                    <select class="form-control input-sm" id="mca-child-account"><option value="">All Connected Accounts</option></select>
                    <select class="form-control input-sm" id="mca-type">
                        <option value="All">All Content</option>
                        <option value="Reels">Reels</option>
                        <option value="Posts">Posts</option>
                    </select>
                    <select class="form-control input-sm" id="mca-comment-filter">
                        <option value="All">All Comments</option>
                        <option value="No Reply">No Reply</option>
                        <option value="Needs Review">Needs Review</option>
                        <option value="Lead Captured">Leads</option>
                        <option value="Failed">Failed</option>
                        <option value="Sent">Sent</option>
                    </select>
                    <input class="form-control input-sm" id="mca-source-search" placeholder="Search posts, reels, captions" />
                    <button class="btn btn-primary btn-sm" id="mca-refresh">Refresh</button>
                </div>
                <div class="mca-feed" id="mca-feed"><div class="mca-empty">Loading posts and reels...</div></div>
            </section>
            <aside class="mca-side" id="mca-side">
                <div class="mca-empty">Click Comments on any post or reel.</div>
            </aside>
        </div>
    `);

    const api = {
        accounts: () => frappe.call("meta_comment_ai.api.inbox.get_accounts"),
        connectedAccounts: (account) => frappe.call("meta_comment_ai.api.inbox.get_connected_accounts", { account }),
        sources: (args) => frappe.call("meta_comment_ai.api.inbox.get_sources", args),
        sourceDetail: (source) => frappe.call("meta_comment_ai.api.inbox.get_source_detail", { source }),
        comments: (args) => frappe.call("meta_comment_ai.api.inbox.get_comments", args),
        detail: (comment) => frappe.call("meta_comment_ai.api.inbox.get_comment_detail", { comment }),
        action: (args) => frappe.call({ method: "meta_comment_ai.api.review.create_comment_action", type: "POST", args }),
        ai: (comment_name) => frappe.call("meta_comment_ai.api.review.generate_ai_action", { comment_name }),
        approve: (action_name) => frappe.call("meta_comment_ai.api.review.approve_action", { action_name }),
        refresh: (account) => frappe.call("meta_comment_ai.api.account.start_background_sync", { account }),
        syncSource: (source) => frappe.call("meta_comment_ai.api.sync.sync_source_comments", { source }),
    };

    function loadAccounts() {
        return api.accounts().then((r) => {
            const accounts = r.message || [];
            const options = ['<option value="">All Master Accounts</option>'].concat(accounts.map((a) => {
                const suffix = a.connected_count ? `${a.connected_count} connected` : (a.can_sync ? a.platform : "Setup");
                const label = frappe.utils.escape_html(`${a.account_label || a.account_name} (${suffix})`);
                return `<option value="${frappe.utils.escape_html(a.name)}">${label}</option>`;
            }));
            $("#mca-account").html(options.join(""));
            restoreSelectValue("#mca-account", savedState.account);
            return loadConnectedAccounts();
        });
    }

    function loadConnectedAccounts() {
        const account = $("#mca-account").val() || null;
        if (!account) {
            $("#mca-child-account").html('<option value="">All Connected Accounts</option>');
            return Promise.resolve();
        }
        return api.connectedAccounts(account).then((r) => {
            const rows = r.message || [];
            const options = ['<option value="">All Connected Accounts</option>'].concat(rows.map((a) => {
                const label = frappe.utils.escape_html(`${a.account_label || a.account_name} (${a.platform || ""})`);
                return `<option value="${frappe.utils.escape_html(a.name)}">${label}</option>`;
            }));
            $("#mca-child-account").html(options.join(""));
            restoreSelectValue("#mca-child-account", savedState.child_account);
        });
    }

    function loadSources() {
        $("#mca-feed").html('<div class="mca-empty">Loading posts and reels...</div>');
        return api.sources({
            account: $("#mca-account").val() || null,
            child_account: $("#mca-child-account").val() || null,
            content_type: $("#mca-type").val() || "All",
            comment_filter: $("#mca-comment-filter").val() || "All",
        }).then((r) => {
            sources = r.message || [];
            renderSourceCards();
            restoreOpenSelection();
        });
    }

    function renderSourceCards() {
        const term = ($("#mca-source-search").val() || "").toLowerCase().trim();
        const rows = sources.filter((s) => !term || [s.source_label, s.message, s.account_label, s.source_id].join(" ").toLowerCase().includes(term));
        if (!rows.length) {
            $("#mca-feed").html('<div class="mca-empty">No posts or reels found yet. Save a token in Social Account and wait for background sync.</div>');
            return;
        }
        $("#mca-feed").html(rows.map(renderSourceCard).join(""));
        $(".mca-comments-btn").on("click", function() {
            const sourceName = $(this).data("source");
            selectedSource = sources.find((s) => s.name === sourceName);
            selectedComment = null;
            saveState({ selected_source: sourceName, selected_comment: null });
            loadSourceComments(sourceName);
        });
        $(".mca-sync-source-btn").on("click", function() {
            syncSourceComments($(this).data("source"), $(this));
        });
    }

    function renderSourceCard(source) {
        const image = source.thumbnail_url || source.media_url || "";
        const platform = (source.platform || "").toLowerCase();
        const commentCount = source.imported_comment_count || 0;
        const metaCount = source.comment_count || 0;
        const caption = source.message || source.source_label || "";
        return `
            <article class="mca-card">
                <div class="mca-card-media">
                    ${image ? `<img src="${frappe.utils.escape_html(image)}" loading="lazy" />` : `<span class="text-muted">${frappe.utils.escape_html(source.source_type || "Post")}</span>`}
                </div>
                <div class="mca-card-body">
                    <div class="mca-card-head">
                        <div class="mca-card-title">${frappe.utils.escape_html(source.account_label || source.social_account || "")}</div>
                        <span class="mca-badge ${platform}">${frappe.utils.escape_html(source.platform || "")}</span>
                    </div>
                    <div class="mca-caption">${frappe.utils.escape_html(caption || "No caption")}</div>
                    <div class="mca-meta">
                        <span>${frappe.utils.escape_html(source.source_type || "")}</span>
                        <span>${dateTimeLabel(source.created_time)}</span>
                        ${source.permalink_url ? `<a href="${frappe.utils.escape_html(source.permalink_url)}" target="_blank">Open on Meta</a>` : ""}
                    </div>
                    <div class="mca-counts">
                        ${renderCount(commentCount, "Synced")}
                        ${renderCount(metaCount, "Meta")}
                        ${renderCount(source.no_reply_count || 0, "No Reply")}
                        ${renderCount(source.needs_review_count || 0, "Review")}
                        ${renderCount(source.lead_count || 0, "Leads")}
                        ${renderCount(source.sent_count || 0, "Sent")}
                        ${renderCount(source.failed_count || 0, "Failed")}
                    </div>
                    <div class="mca-actions">
                        <button class="btn btn-primary btn-sm mca-comments-btn" data-source="${frappe.utils.escape_html(source.name)}">Comments (${commentCount})</button>
                        <a class="btn btn-default btn-sm" href="/app/meta-content-source/${encodeURIComponent(source.name)}">Record</a>
                        <button class="btn btn-default btn-sm mca-sync-source-btn" data-source="${frappe.utils.escape_html(source.name)}">Sync New Comments</button>
                    </div>
                </div>
            </article>
        `;
    }

    function syncSourceComments(sourceName, $button) {
        const finishLoading = setButtonLoading($button, __("Syncing..."));
        frappe.show_alert({ message: __("Syncing comments for this post/reel..."), indicator: "blue" });
        api.syncSource(sourceName).then((r) => {
            const result = r.message || {};
            frappe.show_alert({
                message: __("Synced {0} comment(s).", [result.imported || 0]),
                indicator: "green",
            });
            loadSources().then(() => {
                if (selectedSource && selectedSource.name === sourceName) {
                    loadSourceComments(sourceName);
                }
            });
        }).always(() => {
            finishLoading();
        });
    }

    function renderCount(value, label) {
        return `<div class="mca-count"><strong>${Number(value || 0)}</strong><span>${frappe.utils.escape_html(label)}</span></div>`;
    }

    function loadSourceComments(sourceName) {
        $("#mca-side").html('<div class="mca-empty">Loading comments...</div>');
        return api.sourceDetail(sourceName).then((r) => {
            const data = r.message || {};
            renderCommentsPanel(data.source, data.comments || []);
            if (savedState.selected_comment && sourceName === savedState.selected_source) {
                const exists = (data.comments || []).some((row) => row.name === savedState.selected_comment);
                if (exists) {
                    selectedComment = savedState.selected_comment;
                    loadCommentDetail(selectedComment);
                    setTimeout(() => {
                        $(`.mca-comment-row[data-comment="${cssEscape(selectedComment)}"]`).addClass("active")[0]?.scrollIntoView({ block: "nearest" });
                    }, 100);
                }
            }
        });
    }

    function renderCommentsPanel(source, comments) {
        if (!source) {
            $("#mca-side").html('<div class="mca-empty">Click Comments on any post or reel.</div>');
            return;
        }
        $("#mca-side").html(`
            <div class="mca-side-head">
                <div class="mca-side-title">${frappe.utils.escape_html(source.account_label || source.social_account || "")}</div>
                <div class="mca-side-subtitle">
                    ${frappe.utils.escape_html(source.source_type || "")} · ${dateTimeLabel(source.created_time)} · ${comments.length} comments
                </div>
                <div class="mca-meta">
                    <span class="mca-badge ${(source.platform || "").toLowerCase()}">${frappe.utils.escape_html(source.platform || "")}</span>
                    ${source.permalink_url ? `<a href="${frappe.utils.escape_html(source.permalink_url)}" target="_blank">Open Post</a>` : ""}
                </div>
            </div>
            <div class="mca-comment-tools">
                <input class="form-control input-sm" id="mca-comment-search" placeholder="Search comments, names, phone numbers" />
                <select class="form-control input-sm" id="mca-status">
                    <option>All</option>
                    <option>No Reply</option>
                    <option>Needs Review</option>
                    <option>Lead Captured</option>
                    <option>Escalated</option>
                    <option>Failed</option>
                    <option>Sent</option>
                </select>
            </div>
            <div class="mca-comment-list" id="mca-comment-list">${renderCommentList(comments)}</div>
            <div class="mca-detail-panel" id="mca-detail-panel"><div class="text-muted">Select a comment to see AI suggestion and actions.</div></div>
        `);
        bindCommentFilters(source.name);
        bindCommentRows();
    }

    function renderCommentList(comments) {
        if (!comments.length) {
            return '<div class="mca-empty">No synced comments for this post/reel yet.</div>';
        }
        return comments.map(renderCommentRow).join("");
    }

    function renderCommentRow(row) {
        const actor = row.commenter_username || row.commenter_name || "Unknown";
        const active = selectedComment === row.name ? "active" : "";
        return `
            <div class="mca-comment-row ${active}" data-comment="${frappe.utils.escape_html(row.name)}">
                <div class="mca-comment-head">
                    <div class="mca-comment-user">${frappe.utils.escape_html(actor)}</div>
                    <div class="mca-comment-status">${frappe.utils.escape_html(row.processing_status || "")}</div>
                </div>
                <div class="mca-comment-text">${frappe.utils.escape_html(row.comment_text || "No text")}</div>
                <div class="mca-meta">
                    <span>${frappe.utils.escape_html(row.risk_category || "")}</span>
                    ${row.phone_numbers ? "<span>Phone lead</span>" : ""}
                    ${row.crm_lead ? `<a href="/app/crm-lead/${encodeURIComponent(row.crm_lead)}">CRM Lead</a>` : ""}
                </div>
            </div>
        `;
    }

    function bindCommentFilters(sourceName) {
        let timer = null;
        $("#mca-comment-search, #mca-status").on("input change", () => {
            clearTimeout(timer);
            timer = setTimeout(() => refreshComments(sourceName), 220);
        });
    }

    function refreshComments(sourceName) {
        return api.comments({
            account: selectedSource ? selectedSource.social_account : null,
            child_account: null,
            source: sourceName,
            status: $("#mca-status").val() === "No Reply" ? "All" : ($("#mca-status").val() || "All"),
            comment_filter: $("#mca-status").val() === "No Reply" ? "No Reply" : "All",
            search: $("#mca-comment-search").val() || null,
            limit: 1000,
        }).then((r) => {
            $("#mca-comment-list").html(renderCommentList(r.message || []));
            bindCommentRows();
        });
    }

    function bindCommentRows() {
        $(".mca-comment-row").on("click", function() {
            selectedComment = $(this).data("comment");
            $(".mca-comment-row").removeClass("active");
            $(this).addClass("active");
            saveState({ selected_comment: selectedComment, selected_source: selectedSource ? selectedSource.name : null });
            loadCommentDetail(selectedComment);
        });
    }

    function loadCommentDetail(comment) {
        $("#mca-detail-panel").html('<div class="text-muted">Loading AI suggestion...</div>');
        api.detail(comment).then((r) => {
            const data = r.message || {};
            renderCommentDetail(data.comment || {}, data.actions || []);
        });
    }

    function renderCommentDetail(c, actions) {
        const title = c.commenter_username || c.commenter_name || c.platform_comment_id;
        const aiActions = actions.filter((a) => a.action_source === "AI");
        $("#mca-detail-panel").html(`
            <div class="mca-detail-title">${frappe.utils.escape_html(title || "Comment")}</div>
            <div class="mca-comment-text">${frappe.utils.escape_html(c.comment_text || "No comment text")}</div>
            <div class="mca-meta">
                <span>${frappe.utils.escape_html(c.processing_status || "")}</span>
                <span>${frappe.utils.escape_html(c.risk_category || "")}</span>
                ${c.permalink_url ? `<a href="${frappe.utils.escape_html(c.permalink_url)}" target="_blank">Open Comment</a>` : ""}
                <a href="/app/meta-comment/${encodeURIComponent(c.name)}">Record</a>
            </div>
            <div style="margin-top: 12px;">
                <div class="mca-detail-title">AI Suggestion</div>
                ${aiActions.length ? renderAction(aiActions[0]) : '<div class="text-muted">Generating safe AI suggestion...</div>'}
            </div>
            <div class="mca-actions">
                <button class="btn btn-default btn-sm" id="mca-ai">Refresh AI</button>
                <button class="btn btn-default btn-sm" id="mca-hide">Hide</button>
                <button class="btn btn-default btn-sm" id="mca-delete">Delete</button>
                <button class="btn btn-default btn-sm" id="mca-escalate">Escalate</button>
            </div>
            <div style="margin-top: 10px;">
                <textarea class="form-control" id="mca-reply-text" rows="3" placeholder="Write a public reply">${frappe.utils.escape_html(replyDraft(aiActions, actions))}</textarea>
                <div class="mca-actions">
                    <button class="btn btn-primary btn-sm" id="mca-send-reply">Send Public Reply</button>
                </div>
            </div>
            <div style="margin-top: 12px;">
                <div class="mca-detail-title">Action History</div>
                ${actions.length ? actions.map(renderAction).join("") : '<div class="text-muted">No actions yet.</div>'}
            </div>
        `);
        bindDetail(c.name);
    }

    function replyDraft(aiActions, actions) {
        const source = (aiActions || []).find((a) => a.reply_text) || (actions || []).find((a) => a.reply_text);
        return source ? source.reply_text : "";
    }

    function renderAction(a) {
        const approve = ["Draft", "Needs Review", "Failed"].includes(a.status)
            ? `<button class="btn btn-xs btn-primary mca-approve" data-action="${frappe.utils.escape_html(a.name)}">Approve</button>`
            : "";
        return `
            <div class="mca-history-row">
                <strong>${frappe.utils.escape_html(a.action_type || "")}</strong>
                <span class="text-muted">${frappe.utils.escape_html(a.status || "")}</span>
                ${approve}
                ${a.reply_text ? `<div>${frappe.utils.escape_html(a.reply_text)}</div>` : ""}
                ${a.error ? `<div class="text-danger">${frappe.utils.escape_html(a.error)}</div>` : ""}
            </div>
        `;
    }

    function bindDetail(commentName) {
        $("#mca-ai").on("click", function() {
            const finishLoading = setButtonLoading($(this), __("Working..."));
            api.ai(commentName).then(() => loadCommentDetail(commentName)).always(finishLoading);
        });
        $("#mca-hide").on("click", function() {
            makeAction(commentName, "hide_comment", "", 1, $(this));
        });
        $("#mca-delete").on("click", () => {
            const $button = $("#mca-delete");
            frappe.confirm(__("Delete this comment on Meta? This cannot be undone."), () => makeAction(commentName, "delete_comment", "", 1, $button));
        });
        $("#mca-escalate").on("click", function() {
            makeAction(commentName, "escalate", "", 1, $(this));
        });
        $("#mca-send-reply").on("click", function() {
            makeAction(commentName, "draft_public_reply", $("#mca-reply-text").val(), 1, $(this));
        });
        $(".mca-approve").on("click", function() {
            const finishLoading = setButtonLoading($(this), __("Working..."));
            api.approve($(this).data("action")).then(() => loadCommentDetail(commentName)).always(finishLoading);
        });
    }

    function makeAction(commentName, actionType, replyText, executeNow, $button) {
        const finishLoading = setButtonLoading($button, __("Working..."));
        api.action({ comment_name: commentName, action_type: actionType, reply_text: replyText, execute_now: executeNow })
            .then((r) => {
                const result = r.message || {};
                if (result.status === "Failed") {
                    frappe.msgprint(result.error || __("Meta action failed."));
                } else if (executeNow) {
                    frappe.show_alert({ message: __("Sent to Meta."), indicator: "green" });
                } else {
                    frappe.show_alert({ message: __("Action saved."), indicator: "green" });
                }
                loadCommentDetail(commentName);
                if (selectedSource) refreshComments(selectedSource.name);
            })
            .always(() => {
                finishLoading();
            });
    }

    function setButtonLoading($button, label) {
        if (!$button || !$button.length) {
            return () => {};
        }
        if ($button.prop("disabled")) {
            return () => {};
        }
        const originalHtml = $button.html();
        $button.prop("disabled", true).addClass("disabled").html(label || __("Working..."));
        return () => {
            $button.prop("disabled", false).removeClass("disabled").html(originalHtml);
        };
    }

    function dateTimeLabel(value) {
        if (!value) return "";
        const d = new Date(value);
        return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
    }

    $("#mca-account").on("change", () => {
        selectedSource = null;
        selectedComment = null;
        $("#mca-side").html('<div class="mca-empty">Click Comments on any post or reel.</div>');
        saveState({ child_account: "", selected_source: null, selected_comment: null });
        loadConnectedAccounts().then(loadSources);
    });
    $("#mca-child-account, #mca-type, #mca-comment-filter").on("change", () => {
        selectedSource = null;
        selectedComment = null;
        $("#mca-side").html('<div class="mca-empty">Click Comments on any post or reel.</div>');
        saveState({ selected_source: null, selected_comment: null });
        loadSources();
    });
    $("#mca-source-search").on("input", frappe.utils.debounce(() => {
        saveState();
        renderSourceCards();
    }, 200));
    $("#mca-refresh").on("click", function() {
        const finishLoading = setButtonLoading($(this), __("Refreshing..."));
        const account = $("#mca-account").val() || null;
        const childAccount = $("#mca-child-account").val() || null;
        api.refresh(childAccount || account).then((r) => {
            frappe.show_alert({ message: __("Background sync queued for {0} account(s).", [r.message.queued || 0]), indicator: "green" });
            setTimeout(loadSources, 1500);
        }).always(finishLoading);
    });

    wrapper.mca_restore_inbox_state = restoreInboxStateFromStorage;
    restoreStaticFilters();
    loadAccounts().then(loadSources);

    function restoreInboxStateFromStorage() {
        if (!$("#mca-account").length) {
            return;
        }
        savedState = loadSavedState();
        restoreStaticFilters();
        restoreSelectValue("#mca-account", savedState.account);
        selectedSource = null;
        selectedComment = null;
        loadConnectedAccounts().then(() => {
            restoreSelectValue("#mca-child-account", savedState.child_account);
            loadSources();
        });
    }

    function restoreStaticFilters() {
        restoreSelectValue("#mca-type", savedState.content_type);
        restoreSelectValue("#mca-comment-filter", savedState.comment_filter);
        $("#mca-source-search").val(savedState.source_search || "");
    }

    function restoreOpenSelection() {
        if (!savedState.selected_source) {
            return;
        }
        const source = sources.find((s) => s.name === savedState.selected_source);
        if (!source) {
            return;
        }
        selectedSource = source;
        loadSourceComments(source.name);
        setTimeout(() => {
            $(`.mca-comments-btn[data-source="${cssEscape(source.name)}"]`)[0]?.scrollIntoView({ block: "center" });
        }, 100);
    }

    function loadSavedState() {
        try {
            return JSON.parse(localStorage.getItem(stateKey) || "{}") || {};
        } catch (e) {
            return {};
        }
    }

    function saveState(extra) {
        const state = {
            account: $("#mca-account").val() || "",
            child_account: $("#mca-child-account").val() || "",
            content_type: $("#mca-type").val() || "All",
            comment_filter: $("#mca-comment-filter").val() || "All",
            source_search: $("#mca-source-search").val() || "",
            selected_source: selectedSource ? selectedSource.name : null,
            selected_comment: selectedComment || null,
            ...(extra || {}),
        };
        savedState = state;
        localStorage.setItem(stateKey, JSON.stringify(state));
    }

    function restoreSelectValue(selector, value) {
        if (value && $(`${selector} option[value="${cssEscape(value)}"]`).length) {
            $(selector).val(value);
        }
    }

    function cssEscape(value) {
        if (window.CSS && CSS.escape) {
            return CSS.escape(value || "");
        }
        return String(value || "").replace(/"/g, '\\"');
    }
};

frappe.pages["meta-comment-inbox"].on_page_show = function(wrapper) {
    if (typeof wrapper.mca_restore_inbox_state === "function") {
        wrapper.mca_restore_inbox_state();
    }
};
