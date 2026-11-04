// Local illustration only. No API requests, credentials or real task state.
(() => {
  const buttons = document.querySelectorAll('[data-example]');
  buttons.forEach(button => button.addEventListener('click', () => {
    const complete = button.dataset.example === 'complete';
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    document.getElementById('se-app-stage').textContent = complete ? 'Verified' : 'Implemented';
    document.getElementById('se-test-stage').textContent = complete ? 'Verified' : 'Blocked';
    document.getElementById('se-result-title').textContent = complete ? 'Reported verified.' : 'Still in progress.';
    document.getElementById('se-result-copy').textContent = complete
      ? 'All required work is reported verified with evidence. The designated authority publishes a separate overall verified result. The endpoint records the claim; it does not independently prove it.'
      : 'One agent has finished. The application release and final checks remain. A completed work item does not complete the task.';
  }));
})();
