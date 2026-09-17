(function () {
  "use strict";

  var state = {
    report: null,
    loading: false,
    branchesLoaded: false,
    changedOnly: false,
    observer: null,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function setStatus(text) {
    var el = $("sdiff-status");
    if (el) el.textContent = text;
  }

  function selectedRef() {
    var commit = $("sdiff-commit");
    var branch = $("sdiff-branch");
    if (commit && commit.value) return commit.value;
    if (branch && branch.value) return branch.value;
    return "HEAD";
  }

  function fetchJson(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () {
          return {};
        }).then(function (body) {
          var msg =
            (body && (body.detail || body.message)) ||
            "Request failed (" + res.status + ")";
          throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
        });
      }
      return res.json();
    });
  }

  function fillSelect(select, items, getValue, getLabel, placeholder) {
    select.innerHTML = "";
    var empty = document.createElement("option");
    empty.value = "";
    empty.textContent = placeholder;
    select.appendChild(empty);
    items.forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = getValue(item);
      opt.textContent = getLabel(item);
      select.appendChild(opt);
    });
  }

  function fillCommits(commits) {
    fillSelect(
      $("sdiff-commit"),
      commits || [],
      function (c) {
        return c.sha;
      },
      function (c) {
        return c.short + " — " + c.subject + " (" + c.relative + ")";
      },
      "— tip of branch (no specific commit) —"
    );
  }

  function loadCommitsForBranch(branchName) {
    if (!branchName) {
      fillCommits([]);
      return Promise.resolve();
    }
    setStatus("Loading commits for " + branchName + "…");
    return fetchJson(
      "/api/swagger-diff/git-refs/?branch=" + encodeURIComponent(branchName)
    ).then(function (data) {
      fillCommits(data.commits || []);
      setStatus(
        "Commits from " +
          (data.branch || branchName) +
          " (" +
          (data.commits || []).length +
          ")"
      );
    });
  }

  function loadRefs() {
    return fetchJson("/api/swagger-diff/git-refs/").then(function (data) {
      fillSelect(
        $("sdiff-branch"),
        data.branches || [],
        function (b) {
          return b;
        },
        function (b) {
          return b === data.head ? b + " (current)" : b;
        },
        "— pick branch —"
      );
      fillCommits(data.commits || []);
      state.branchesLoaded = true;
      if (data.head) {
        $("sdiff-branch").value = data.head;
      }
      setStatus("Baseline default: " + (data.head || "HEAD"));
    });
  }

  function clearBadges() {
    document
      .querySelectorAll(
        ".sdiff-side-tag, .sdiff-badge, .sdiff-label, .sdiff-changes, .sdiff-inline-dot"
      )
      .forEach(function (n) {
        n.remove();
      });
    var box = $("sdiff-removed");
    var list = $("sdiff-removed-list");
    if (box) box.hidden = true;
    if (list) list.innerHTML = "";
    document
      .querySelectorAll(
        ".sdiff-chips .sdiff-chip-new, .sdiff-chips .sdiff-chip-upd, .sdiff-chips .sdiff-chip-del"
      )
      .forEach(function (n) {
        n.remove();
      });
  }

  function findOpblock(method, path) {
    var methodLower = String(method || "").toLowerCase();
    var nodes = document.querySelectorAll(".opblock");
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var m = node.querySelector(".opblock-summary-method");
      var p = node.querySelector(".opblock-summary-path");
      if (!m || !p) continue;
      var methodText = m.textContent.trim().toLowerCase();
      var pathText = p.textContent.trim();
      if (methodText === methodLower && pathText === path) {
        return node;
      }
    }
    return null;
  }

  function badgeClass(status) {
    if (status === "added") return "new";
    if (status === "updated") return "updated";
    return "removed";
  }

  function badgeText(status) {
    if (status === "added") return "NEW";
    if (status === "updated") return "UPDATE";
    return "DELETE";
  }

  function insertSideTag(block, status) {
    var summary = block.querySelector(".opblock-summary");
    if (!summary) return;
    if (summary.querySelector(".sdiff-side-tag")) return;
    var tag = document.createElement("span");
    tag.className = "sdiff-side-tag sdiff-side-tag-" + badgeClass(status);
    tag.textContent = badgeText(status);
    tag.title =
      status === "added"
        ? "New endpoint (not in baseline)"
        : status === "updated"
          ? "Updated endpoint (changed vs baseline)"
          : "Deleted endpoint (only in baseline)";
    summary.insertBefore(tag, summary.firstChild);
  }

  /** Map a DiffReport change into UI effect + area + target name. */
  function enrichChange(c) {
    var kind = c.kind || "";
    var path = c.path || "";
    var effect = c.effect;
    if (!effect) {
      effect =
        kind === "added" ? "new" : kind === "removed" ? "removed" : "updated";
    }
    // Normalize aliases
    if (effect === "added") effect = "new";
    if (effect === "delete" || effect === "deleted") effect = "removed";
    if (effect === "update") effect = "updated";

    var area = c.area || "other";
    if (!c.area) {
      if (path.indexOf("parameters.") === 0) area = "parameter";
      else if (path.indexOf("requestBody") === 0) area = "request";
      else if (path.indexOf("responses.") === 0) area = "response";
      else if (
        path.indexOf("schemas.") === 0 ||
        (c.message || "").indexOf("[schema ") === 0
      )
        area = "schema";
      else if (
        path === "summary" ||
        path === "description" ||
        path === "operationId" ||
        path === "deprecated" ||
        path === "tags"
      )
        area = "meta";
    }
    var target = c.target || "";
    if (!target) {
      var paramMatch = path.match(/^parameters\.[^:]+:([^./]+)/);
      var propMatch = path.match(/\.properties\.([^./]+)/);
      var schemaMatch = (c.message || "").match(/^\[schema ([^\]]+)\]/);
      var statusMatch = path.match(/^responses\.([^./]+)/);
      var quoted = (c.message || "").match(/Property "([^"]+)"/);
      if (paramMatch) target = paramMatch[1];
      else if (propMatch) target = propMatch[1];
      else if (quoted) target = quoted[1];
      else if (schemaMatch) target = schemaMatch[1];
      else if (statusMatch) target = "HTTP " + statusMatch[1];
    }
    var effectLabel =
      effect === "new" ? "NEW" : effect === "removed" ? "DELETE" : "UPDATE";
    return {
      raw: c,
      effect: effect,
      effectLabel: effectLabel,
      area: area,
      target: target,
      message: c.message || kind,
    };
  }

  function areaTitle(area) {
    if (area === "parameter") return "Parameters";
    if (area === "request") return "Request body";
    if (area === "response") return "Responses";
    if (area === "schema") return "Response / schema objects";
    if (area === "meta") return "Operation metadata";
    return "Other";
  }

  function buildChangesPanel(changes) {
    var wrap = document.createElement("div");
    wrap.className = "sdiff-changes";

    var title = document.createElement("div");
    title.className = "sdiff-changes-title";
    title.textContent = "What changed vs baseline";
    wrap.appendChild(title);

    var enriched = (changes || []).map(enrichChange);
    var groups = {};
    var order = ["parameter", "request", "response", "schema", "meta", "other"];
    enriched.forEach(function (e) {
      if (!groups[e.area]) groups[e.area] = [];
      groups[e.area].push(e);
    });

    order.forEach(function (area) {
      var items = groups[area];
      if (!items || !items.length) return;
      var group = document.createElement("div");
      group.className = "sdiff-change-group";
      var h = document.createElement("h5");
      h.textContent = areaTitle(area);
      group.appendChild(h);
      items.slice(0, 50).forEach(function (e) {
        var row = document.createElement("div");
        row.className = "sdiff-change-row";
        row.innerHTML =
          '<span class="sdiff-dot sdiff-dot-' +
          e.effect +
          '" title="' +
          e.effectLabel +
          '"></span>' +
          '<span class="sdiff-effect sdiff-effect-' +
          e.effect +
          '">' +
          e.effectLabel +
          "</span>" +
          '<span class="sdiff-change-msg">' +
          (e.target
            ? '<span class="sdiff-change-target">' +
              e.target +
              "</span> — "
            : "") +
          escapeHtml(e.message) +
          "</span>";
        group.appendChild(row);
      });
      wrap.appendChild(group);
    });

    return wrap;
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function makeInlineDot(effect, title) {
    var dot = document.createElement("span");
    dot.className = "sdiff-inline-dot sdiff-inline-dot-" + effect;
    dot.title = title || effect;
    return dot;
  }

  function collectTargetEffects(changes) {
    var byTarget = {};
    var rank = { new: 3, removed: 3, updated: 1 };
    (changes || []).map(enrichChange).forEach(function (e) {
      if (!e.target) return;
      var prev = byTarget[e.target];
      if (!prev || (rank[e.effect] || 0) >= (rank[prev] || 0)) {
        // Prefer explicit add/remove over update when both exist
        if (prev === "new" || prev === "removed") {
          if (e.effect === "new" || e.effect === "removed") {
            byTarget[e.target] = e.effect;
          }
        } else {
          byTarget[e.target] = e.effect;
        }
      }
    });
    return byTarget;
  }

  /** Put colored dots on keys inside the black Example Value JSON panel. */
  function annotateExampleBlocks(block, changes) {
    var targets = collectTargetEffects(changes);
    var keys = Object.keys(targets);
    if (!keys.length) return;

    // Only real code nodes — never light wrapper divs like .example
    var nodes = block.querySelectorAll(
      "pre.microlight, pre.body-param__example, .highlight-code > pre, pre"
    );
    var seen = [];
    nodes.forEach(function (pre) {
      if (!pre || seen.indexOf(pre) !== -1) return;
      // Skip if nested inside another matched pre
      if (pre.parentElement && pre.parentElement.closest && pre.parentElement.closest("pre") && pre.parentElement.closest("pre") !== pre) {
        return;
      }
      seen.push(pre);
      if (pre.dataset.sdiffAnnotated === "1") return;

      var raw = pre.dataset.sdiffRaw || pre.textContent || "";
      if (!raw || raw.indexOf("{") === -1) return;

      var lines = raw.split("\n");
      var present = {};
      var htmlLines = lines.map(function (line) {
        var m = line.match(/^(\s*)"([^"\\]+)"(\s*:)(.*)$/);
        if (m && targets[m[2]]) {
          present[m[2]] = true;
          var effect = targets[m[2]];
          return (
            escapeHtml(m[1]) +
            '<span class="sdiff-json-line sdiff-json-line-' +
            effect +
            '">' +
            '<span class="sdiff-inline-dot sdiff-inline-dot-' +
            effect +
            '" title="' +
            (effect === "new"
              ? "NEW — added field"
              : effect === "removed"
                ? "DELETE — removed field"
                : "UPDATE — field changed") +
            '"></span>' +
            '<span class="sdiff-json-key">"' +
            escapeHtml(m[2]) +
            '"</span>' +
            escapeHtml(m[3]) +
            escapeHtml(m[4]) +
            "</span>"
          );
        }
        // Keep JSON looking like code on dark bg
        return escapeHtml(line).replace(
          /^(\s*)(&quot;[^&]+&quot;)/,
          '$1<span class="sdiff-json-key">$2</span>'
        );
      });

      var removedMissing = keys.filter(function (k) {
        return targets[k] === "removed" && !present[k] && raw.indexOf('"' + k + '"') === -1;
      });
      if (removedMissing.length && htmlLines.length) {
        var ghosts = removedMissing.map(function (k) {
          return (
            "  " +
            '<span class="sdiff-json-line sdiff-json-line-removed sdiff-json-ghost">' +
            '<span class="sdiff-inline-dot sdiff-inline-dot-removed" title="DELETE — removed field"></span>' +
            '<span class="sdiff-json-key">"' +
            escapeHtml(k) +
            '"</span>: /* removed vs baseline */' +
            "</span>"
          );
        });
        htmlLines.splice(1, 0, ghosts.join("\n"));
      }

      pre.innerHTML = htmlLines.join("\n");
      pre.dataset.sdiffAnnotated = "1";
      pre.classList.add("sdiff-example-annotated", "microlight");
    });
  }

  /** Paint colored dots on Swagger parameter names / model props / example JSON. */
  function decorateSwaggerDetails(block, changes) {
    if (!block || !changes || !changes.length) return;
    block.querySelectorAll(".sdiff-inline-dot").forEach(function (n) {
      // Keep dots inside already-annotated example lines; re-annotate from scratch
      n.remove();
    });
    block.querySelectorAll("[data-sdiff-annotated='1']").forEach(function (el) {
      // Reset so we can re-apply with fresh effects
      if (el.dataset.sdiffRaw) {
        el.textContent = el.dataset.sdiffRaw;
      }
      delete el.dataset.sdiffAnnotated;
    });

    // Store raw text once before first annotate — only on <pre> code nodes
    block
      .querySelectorAll("pre.microlight, pre.body-param__example, .highlight-code > pre, pre")
      .forEach(function (pre) {
        if (!pre.dataset.sdiffRaw) {
          pre.dataset.sdiffRaw = pre.textContent || "";
        } else if (pre.dataset.sdiffAnnotated === "1") {
          pre.textContent = pre.dataset.sdiffRaw;
          delete pre.dataset.sdiffAnnotated;
          pre.classList.remove("sdiff-example-annotated");
        }
      });

    annotateExampleBlocks(block, changes);

    var byTarget = collectTargetEffects(changes);
    Object.keys(byTarget).forEach(function (name) {
      var effect = byTarget[name];
      var selectors = [
        ".parameter__name",
        ".parameters-col_name",
        ".prop-name",
        ".model .property",
        "span.prop",
        ".model-title__text",
        ".model-box .model-title",
      ];
      selectors.forEach(function (sel) {
        block.querySelectorAll(sel).forEach(function (el) {
          var text = (el.textContent || "").replace(/\*/g, "").trim();
          var propName = text.split(/\s+/)[0];
          if (propName === name || text === name || text.indexOf(name) === 0) {
            if (el.querySelector(".sdiff-inline-dot")) return;
            el.insertBefore(
              makeInlineDot(
                effect,
                (effect === "new"
                  ? "NEW"
                  : effect === "removed"
                    ? "DELETE"
                    : "UPDATE") +
                  ": " +
                  name
              ),
              el.firstChild
            );
          }
        });
      });
    });
  }

  function watchOpenBlocks() {
    if (state.observer) return;
    var root = document.getElementById("swagger-ui") || document.body;
    state.observer = new MutationObserver(function (mutations) {
      var needDecorate = {};
      mutations.forEach(function (m) {
        var el = m.target;
        if (el && el.classList && el.classList.contains("opblock") && el.classList.contains("is-open")) {
          var key = el.getAttribute("data-sdiff-key");
          if (key) needDecorate[key] = el;
        }
        // Example panel may render after open — climb to opblock
        var node = el.nodeType === 1 ? el : el.parentElement;
        while (node && node !== root) {
          if (node.classList && node.classList.contains("opblock") && node.classList.contains("is-open")) {
            var k2 = node.getAttribute("data-sdiff-key");
            if (k2) needDecorate[k2] = node;
            break;
          }
          node = node.parentElement;
        }
      });
      Object.keys(needDecorate).forEach(function (key) {
        if (!state.report || !state.report.paths[key]) return;
        var op = state.report.paths[key];
        if (op.status !== "updated") return;
        window.setTimeout(function () {
          decorateSwaggerDetails(needDecorate[key], op.changes || []);
        }, 100);
      });
    });
    state.observer.observe(root, {
      attributes: true,
      attributeFilter: ["class"],
      childList: true,
      subtree: true,
    });
  }

  function indexAllOpblocks(report) {
    var paths = (report && report.paths) || {};
    document.querySelectorAll(".opblock").forEach(function (block) {
      var m = block.querySelector(".opblock-summary-method");
      var p = block.querySelector(".opblock-summary-path");
      if (!m || !p) return;
      var key = m.textContent.trim().toUpperCase() + " " + p.textContent.trim();
      var op = paths[key];
      block.setAttribute("data-sdiff-key", key);
      block.setAttribute("data-sdiff-status", op ? op.status : "unchanged");
    });
  }

  function applyChangedFilter(changedOnly) {
    state.changedOnly = !!changedOnly;
    document.querySelectorAll(".opblock").forEach(function (block) {
      var st = block.getAttribute("data-sdiff-status") || "unchanged";
      var show = !state.changedOnly || st !== "unchanged";
      block.classList.toggle("sdiff-hidden-unchanged", !show);
    });
    document.querySelectorAll(".opblock-tag-section").forEach(function (section) {
      var visible = false;
      section.querySelectorAll(".opblock").forEach(function (op) {
        if (!op.classList.contains("sdiff-hidden-unchanged")) visible = true;
      });
      section.classList.toggle("sdiff-hidden-section", state.changedOnly && !visible);
    });
    // Models block is noisy when focusing on endpoint diffs
    document.querySelectorAll(".models, section.models").forEach(function (el) {
      el.style.display = state.changedOnly ? "none" : "";
    });
    var btn = $("sdiff-filter-toggle");
    if (btn) {
      btn.hidden = !state.report;
      btn.textContent = state.changedOnly ? "Show all APIs" : "Changed only";
    }
  }

  function applyReport(report) {
    clearBadges();
    state.report = report;
    var summary = report.summary || {};
    var chips = $("schema-diff-bar").querySelector(".sdiff-chips");
    function addChip(cls, text, title) {
      var span = document.createElement("span");
      span.className = "sdiff-chip " + cls;
      span.textContent = text;
      if (title) span.title = title;
      chips.insertBefore(span, $("sdiff-status"));
    }
    addChip(
      "sdiff-chip-new",
      "NEW +" + (summary.added || 0),
      "Endpoints added in current vs baseline"
    );
    addChip(
      "sdiff-chip-upd",
      "UPDATE ~" + (summary.updated || 0),
      "Endpoints that exist in both but changed"
    );
    addChip(
      "sdiff-chip-del",
      "DELETE -" + (summary.removed || 0),
      "Endpoints removed (in baseline, not in current)"
    );
    setStatus("vs " + (report.baseline_ref || "baseline"));

    indexAllOpblocks(report);

    var removed = [];
    Object.keys(report.paths || {}).forEach(function (key) {
      var op = report.paths[key];
      if (op.status === "unchanged") return;
      if (op.status === "removed") {
        removed.push(op);
        return;
      }
      var block = findOpblock(op.method, op.path);
      if (!block) return;
      block.setAttribute("data-sdiff-key", key);
      block.setAttribute("data-sdiff-status", op.status);
      insertSideTag(block, op.status);

      if (op.status === "updated" && op.changes && op.changes.length) {
        block.appendChild(buildChangesPanel(op.changes));
        if (block.classList.contains("is-open")) {
          decorateSwaggerDetails(block, op.changes);
        }
      }
    });

    if (removed.length) {
      var box = $("sdiff-removed");
      var list = $("sdiff-removed-list");
      box.hidden = false;
      removed.forEach(function (op) {
        var row = document.createElement("div");
        row.className = "sdiff-removed-row";
        row.innerHTML =
          '<span class="sdiff-side-tag sdiff-side-tag-removed">DELETE</span>' +
          "<span>" +
          op.method +
          " " +
          op.path +
          "</span>";
        list.appendChild(row);
      });
    }

    // After Compare: show only changed endpoints (NEW / UPDATE); DELETE stays in panel below
    applyChangedFilter(true);
    watchOpenBlocks();
  }

  function compare() {
    if (state.loading) return;
    var ref = selectedRef();
    var btn = $("sdiff-compare");
    state.loading = true;
    if (btn) btn.disabled = true;
    setStatus("Generating baseline schema for " + ref + "… (first time can take a bit)");
    fetchJson("/api/swagger-diff/diff/?ref=" + encodeURIComponent(ref))
      .then(function (report) {
        applyReport(report);
      })
      .catch(function (err) {
        setStatus(err.message || String(err));
      })
      .finally(function () {
        state.loading = false;
        if (btn) btn.disabled = false;
      });
  }

  function bind() {
    var branch = $("sdiff-branch");
    var commit = $("sdiff-commit");
    if (branch) {
      branch.addEventListener("change", function () {
        if (!branch.value) {
          fillCommits([]);
          return;
        }
        // Keep branch selected; reload that branch's commits.
        if (commit) commit.value = "";
        loadCommitsForBranch(branch.value).catch(function (err) {
          setStatus(err.message || String(err));
        });
      });
    }
    if (commit) {
      commit.addEventListener("change", function () {
        // Specific commit wins over branch tip for Compare.
        if (commit.value) {
          setStatus("Baseline commit: " + commit.options[commit.selectedIndex].text);
        }
      });
    }
    var btn = $("sdiff-compare");
    if (btn) btn.addEventListener("click", compare);
    var filterBtn = $("sdiff-filter-toggle");
    if (filterBtn) {
      filterBtn.addEventListener("click", function () {
        applyChangedFilter(!state.changedOnly);
      });
    }
    var drawerBtn = $("sdiff-drawer-toggle");
    var bar = $("schema-diff-bar");
    if (drawerBtn && bar) {
      drawerBtn.addEventListener("click", function () {
        var collapsed = bar.classList.toggle("is-collapsed");
        bar.classList.toggle("is-open", !collapsed);
        drawerBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
        drawerBtn.textContent = collapsed ? "Show ▾" : "Hide ▴";
      });
    }
  }

  function boot() {
    if (!$("schema-diff-bar")) return;
    bind();
    loadRefs().catch(function (err) {
      setStatus(err.message || String(err));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
