// ==UserScript==
// @name         Universal Knowledge Ingestor (SQLite Edition)
// @namespace    http://tampermonkey.net/
// @version      2.2
// @description  Adapts to Reddit, GitHub, YouTube. Sends Markdown to Python/SQLite with Toast notifications.
// @author       Architect
// @match        *://*.reddit.com/*
// @match        *://*.reddit.com/r/*/comments/*
// @match        *://*.reddit.com/user/*/comments/*
// @match        *://*.reddit.com/comments/*
// @match        *://github.com/*
// @match        *://www.youtube.com/watch*
// @require      https://unpkg.com/turndown/dist/turndown.js
// @require      https://unpkg.com/turndown-plugin-gfm/dist/turndown-plugin-gfm.js
// @require      https://unpkg.com/@mozilla/readability/Readability.js
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @run-at       document-idle
// ==/UserScript==

// --- TRUSTED TYPES BYPASS ---
if (window.trustedTypes && window.trustedTypes.createPolicy) {
    if (!window.trustedTypes.defaultPolicy) {
        window.trustedTypes.createPolicy('default', {
            createHTML: (string) => string,
            createScriptURL: (string) => string,
            createScript: (string) => string,
        });
    }
}

(function() {
    'use strict';

    if (window.self !== window.top) return;


    const CONFIG = {
        SERVER_URL: "http://localhost:3002",
        SPA_TIMEOUT: 5000
    };

    // ==========================================
    // UI UTILS: TOAST NOTIFICATIONS
    // ==========================================
    function showToast(message, isError) {
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.position = 'fixed';
        toast.style.bottom = '20px';
        toast.style.right = '20px';
        toast.style.padding = '12px 24px';
        toast.style.borderRadius = '8px';
        toast.style.color = '#fff';
        toast.style.fontFamily = 'system-ui, -apple-system, sans-serif';
        toast.style.fontSize = '14px';
        toast.style.fontWeight = '500';
        toast.style.zIndex = '2147483647';
        toast.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s ease-in-out, transform 0.3s ease-out';
        toast.style.transform = 'translateY(10px)';
        toast.style.backgroundColor = isError ? '#ef4444' : '#22c55e';

        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateY(0)';
        }, 10);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // ==========================================
    // MARKDOWN ENGINE SETUP
    // ==========================================
    const turndownService = new TurndownService({
        headingStyle: 'atx',
        codeBlockStyle: 'fenced'
    });
    turndownService.use(turndownPluginGfm.gfm);

    function queryDeep(selector, root = document) {
        let found = root.querySelector(selector);
        if (found) return found;
        const shadows = Array.from(root.querySelectorAll('*')).map(el => el.shadowRoot).filter(Boolean);
        for (const shadow of shadows) {
            let inner = queryDeep(selector, shadow);
            if (inner) return inner;
        }
        return null;
    }

    // ==========================================
    // ADAPTERS
    // ==========================================

    class BaseAdapter {
        constructor() { this.domain = window.location.hostname; }
        isMatch() { return false; }
        async parse() { throw new Error("Not implemented"); }
    }

    // --- ROBUST REDDIT ADAPTER ---
    class RedditAdapter extends BaseAdapter {

        isMatch() {
            const url = window.location.href;
            // This ensures the logic ONLY fires if "/comments/" is in the URL
            // regardless of whether the script is technically "active" on the homepage.
            return (
                this.domain.includes('reddit.com') &&
                url.includes('/comments/') &&
                !url.includes('/comments/id/title/comment-id') // avoids matching direct links to single comments if desired
            );
        }

        async parse() {
            // 1. Identify the specific Post ID from the URL to avoid scraping background feeds
            // URL format: /r/Subreddit/comments/[POST_ID]/[TITLE]/
            const urlParts = window.location.pathname.split('/comments/');
            const postId = urlParts[1] ? urlParts[1].split('/')[0] : null;

            if (!postId) throw new Error("Could not extract Post ID from URL");

            console.log(`[RedditAdapter] Targeting Post ID: ${postId}`);

            // 2. Find the specific <shreddit-post> element that matches this ID or Permalink
            // Modern Reddit uses the 'permalink' attribute on the host element.
            const postSelector = `shreddit-post[permalink*="${postId}"]`;

            // Wait up to 5 seconds for the specific post to appear in DOM
            const postElement = await this.waitFor(postSelector, 5000);

            if (!postElement) throw new Error(`Active post element (${postId}) not found in DOM`);

            // 3. Extract Content SCOPED to this post element
            const title = postElement.getAttribute('post-title') || document.title;

            // The body is often inside a div with slot="text-body" inside the shadow or light DOM
            const bodySlot = postElement.querySelector('div[slot="text-body"]');
            const postMarkdown = bodySlot ? turndownService.turndown(bodySlot.innerHTML) : "";

            // 4. Extract Comments (scoped to the comment tree associated with this post)
            // We look for the comment tree sibling or child
            const commentTree = document.querySelector('shreddit-comment-tree') || postElement.parentElement.querySelector('shreddit-comment-tree');

            let comments = [];
            if (commentTree) {
                // Get only top-level comments or the first batch of loaded comments
                // We use the custom element <shreddit-comment>
                const commentNodes = commentTree.querySelectorAll('shreddit-comment');

                comments = Array.from(commentNodes).map(c => {
                    // content is usually in a slot="comment"
                    const contentSlot = c.querySelector('div[slot="comment"]');
                    const rawHtml = contentSlot ? contentSlot.innerHTML : "";

                    // Cleanup Reddit specific junk (optional)
                    return {
                        author: c.getAttribute('author'),
                        score: c.getAttribute('score'),
                        body: turndownService.turndown(rawHtml),
                        depth: c.getAttribute('depth') || 0
                    };
                });
            }

            return {
                title: title,
                content_markdown: postMarkdown,
                metadata: {
                    type: "reddit_thread",
                    subreddit: postElement.getAttribute('subreddit-prefixed-name'),
                    author: postElement.getAttribute('author'),
                    upvote_ratio: postElement.getAttribute('upvote-ratio'),
                    comment_count: comments.length,
                    comments: comments
                }
            };
        }

        // Helper to wait for dynamic elements (Hydration fix)
        waitFor(selector, timeout = 3000) {
            return new Promise((resolve) => {
                if (document.querySelector(selector)) return resolve(document.querySelector(selector));

                const observer = new MutationObserver(() => {
                    if (document.querySelector(selector)) {
                        observer.disconnect();
                        resolve(document.querySelector(selector));
                    }
                });

                observer.observe(document.body, { childList: true, subtree: true });

                setTimeout(() => {
                    observer.disconnect();
                    resolve(null);
                }, timeout);
            });
        }
    }
    class GitHubAdapter extends BaseAdapter {
        isMatch() { return this.domain.includes('github.com'); }
        async parse() {
            const container = document.querySelector('.js-discussion') || document.querySelector('#readme');
            if (!container) throw new Error("GitHub content not found");
            return {
                title: document.title,
                content_markdown: turndownService.turndown(container.innerHTML),
                metadata: { type: "github", repo: window.location.pathname }
            };
        }
    }

    class YouTubeAdapter extends BaseAdapter {
        isMatch() {
            const url = new URL(window.location.href);
            // Strict check: must be a watch page with a video ID
            return (
                this.domain.includes('youtube.com') &&
                url.pathname === '/watch' &&
                url.searchParams.has('v')
            );
        }

        async parse() {
            // We rely 100% on the Python backend (yt-dlp) for content.
            // We just send the URL and a placeholder title.

            const videoId = new URLSearchParams(window.location.search).get('v');

            return {
                title: document.title.replace(" - YouTube", ""), // Temporary client-side title
                content_markdown: "Processing on server...", // Placeholder
                metadata: {
                    type: "youtube_video",
                    video_id: videoId,
                    note: "Server-side processing requested"
                }
            };
        }
    }

    class GenericAdapter extends BaseAdapter {
        isMatch() { return true; }

        async parse() {
            try {
                // Create a clean clone for Readability
                const docClone = document.cloneNode(true);
                const article = new Readability(docClone).parse();

                if (!article) throw new Error("Readability could not extract content");

                return {
                    title: article.title,
                    content_markdown: turndownService.turndown(article.content),
                    metadata: { type: "generic_article" }
                };
            } catch (err) {
                // If Readability fails (common on SPAs), just grab the basic info
                return {
                    title: document.title,
                    content_markdown: "Extraction failed. URL preserved.",
                    metadata: { type: "placeholder", error: err.message }
                };
            }
        }
    }

    // ==========================================
    // CORE ENGINE
    // ==========================================

    class IngestorEngine {
        constructor() {
            this.adapters = [new RedditAdapter(), new GitHubAdapter(), new YouTubeAdapter()];
            this.genericAdapter = new GenericAdapter();
        }

        async run() {
            const adapter = this.adapters.find(a => a.isMatch()) || this.genericAdapter;
            console.log(`[Ingestor] Active Adapter: ${adapter.constructor.name}`);

            try {
                const data = await adapter.parse();
                this.sendData({
                    url: window.location.href,
                    domain: window.location.hostname,
                    ...data
                });
            } catch (e) {
                console.warn("[Ingestor] Adapter failed, trying Generic fallback.");
                try {
                    const fallback = await this.genericAdapter.parse();
                    this.sendData({
                        url: window.location.href,
                        domain: window.location.hostname,
                        ...fallback
                    });
                } catch (err) {
                    showToast("Failed to parse content.", true);
                }
            }
        }

        sendData(payload) {
            GM_xmlhttpRequest({
                method: "POST",
                url: CONFIG.SERVER_URL,
                data: JSON.stringify(payload),
                headers: { "Content-Type": "application/json" },
                onload: (res) => {
                    if (res.status === 200) {
                        showToast(`Archived: ${payload.title.substring(0, 30)}...`, false);
                    } else {
                        showToast("Server error saving page.", true);
                    }
                },
                onerror: () => {
                    showToast("Backend Server Offline", true);
                }
            });
        }
    }

    // ==========================================
    // INIT
    // ==========================================
    const engine = new IngestorEngine();
    let lastUrl = location.href;
    let timeoutId = null;

    function schedule() {
        if (timeoutId) clearTimeout(timeoutId);
        timeoutId = setTimeout(() => engine.run(), CONFIG.SPA_TIMEOUT);
    }

    new MutationObserver(() => {
        if (location.href !== lastUrl) {
            lastUrl = location.href;
            schedule();
        }
    }).observe(document, { subtree: true, childList: true });

    schedule();

})();