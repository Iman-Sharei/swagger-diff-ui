(function () {
  "use strict";

  function getPathText(pathElement) {
    if (!pathElement) {
      return "";
    }
    return pathElement.textContent ? pathElement.textContent.trim() : "";
  }

  function copyText(text) {
    if (!text) {
      return Promise.resolve(false);
    }

    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () {
        return true;
      }).catch(function () {
        return false;
      });
    }

    var tempInput = document.createElement("input");
    tempInput.value = text;
    tempInput.setAttribute("readonly", "readonly");
    tempInput.style.position = "absolute";
    tempInput.style.left = "-9999px";
    document.body.appendChild(tempInput);
    tempInput.select();

    var copied = false;
    try {
      copied = document.execCommand("copy");
    } catch (error) {
      copied = false;
    }

    document.body.removeChild(tempInput);
    return Promise.resolve(copied);
  }

  function setCopiedState(button) {
    var originalLabel = button.getAttribute("data-original-label") || "Copy";
    button.classList.add("is-copied");
    button.textContent = "Copied";

    window.setTimeout(function () {
      button.classList.remove("is-copied");
      button.textContent = originalLabel;
    }, 1200);
  }

  function createButton(pathText) {
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy-path-btn";
    button.textContent = "Copy";
    button.setAttribute("title", "Copy endpoint path");
    button.setAttribute("data-original-label", "Copy");

    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();

      copyText(pathText).then(function (copied) {
        if (copied) {
          setCopiedState(button);
        }
      });
    });

    return button;
  }

  function injectCopyButtons() {
    var pathNodes = document.querySelectorAll(".opblock-summary-path");

    pathNodes.forEach(function (pathNode) {
      if (pathNode.parentElement && pathNode.parentElement.querySelector(".copy-path-btn")) {
        return;
      }

      var pathText = getPathText(pathNode);
      if (!pathText || !pathNode.parentElement) {
        return;
      }

      pathNode.parentElement.appendChild(createButton(pathText));
    });
  }

  function init() {
    injectCopyButtons();
    var observer = new MutationObserver(function () {
      injectCopyButtons();
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
    return;
  }

  init();
})();
