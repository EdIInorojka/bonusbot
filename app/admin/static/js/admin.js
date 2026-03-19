(() => {
  const forms = document.querySelectorAll("form[data-confirm]");
  forms.forEach((f) => {
    f.addEventListener("submit", (e) => {
      const msg = f.dataset.confirm;
      if (msg && !confirm(msg)) {
        e.preventDefault();
      }
    });
  });
})();
