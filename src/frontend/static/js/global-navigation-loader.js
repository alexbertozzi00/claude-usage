(function initGlobalNavigationLoader() {
  function hideGlobalLoadingOverlayForStaticPages() {
    if (typeof setGlobalLoading === 'function') {
      setGlobalLoading(false);
      return;
    }
    const overlay = document.getElementById('global-loading-overlay');
    if (overlay) {
      overlay.classList.remove('is-visible');
      overlay.setAttribute('aria-busy', 'false');
    }
    document.body?.classList.remove('global-loading-active');
  }

  function showGlobalLoadingOverlay() {
    if (typeof setGlobalLoading === 'function') {
      setGlobalLoading(true);
      return;
    }
    const overlay = document.getElementById('global-loading-overlay');
    if (overlay) {
      overlay.classList.add('is-visible');
      overlay.setAttribute('aria-busy', 'true');
    }
    document.body?.classList.add('global-loading-active');
  }

  function shouldHandleNavigationClick(event, link) {
    if (!link) return false;
    if (event.defaultPrevented) return false;
    if (event.button !== 0) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    if (link.getAttribute('target') === '_blank') return false;

    const href = (link.getAttribute('href') || '').trim();
    if (!href || href === '/' || href.startsWith('#')) return false;

    return href.startsWith('/');
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest("a[href^='/']");
    if (!shouldHandleNavigationClick(event, link)) return;
    showGlobalLoadingOverlay();
  }, true);

  window.addEventListener('beforeunload', () => {
    showGlobalLoadingOverlay();
  });

  window.addEventListener('DOMContentLoaded', () => {
    hideGlobalLoadingOverlayForStaticPages();
  });

  window.addEventListener('pageshow', () => {
    hideGlobalLoadingOverlayForStaticPages();
  });
})();
