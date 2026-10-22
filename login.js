/* ── SecureBank Admin Login ───────────────────────────────────── */

// ── Admin credentials (demo — change for production) ───────────
const ADMIN_USER = 'Admin21';
const ADMIN_PASS = 'admins';

// ── Theme (shared with dashboard via localStorage) ─────────────
(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem('sb-theme');
  // Login page is dark-first; map 'light' → data-theme="light"
  if (saved === 'light') root.setAttribute('data-theme', 'light');

  document.addEventListener('DOMContentLoaded', function () {
    // If already logged in, skip to dashboard
    if (localStorage.getItem('sb-admin-auth') === '1') {
      window.location.replace('index.html');
      return;
    }

    // Theme toggle
    const themeBtn = document.getElementById('themeToggleLogin');
    themeBtn && themeBtn.addEventListener('click', function () {
      const isLight = root.getAttribute('data-theme') === 'light';
      if (isLight) {
        root.removeAttribute('data-theme');
        localStorage.setItem('sb-theme', 'dark');
      } else {
        root.setAttribute('data-theme', 'light');
        localStorage.setItem('sb-theme', 'light');
      }
    });

    // Eye button (show/hide password)
    const eyeBtn  = document.getElementById('eyeBtn');
    const passIn  = document.getElementById('password');
    eyeBtn && eyeBtn.addEventListener('click', function () {
      const shown = passIn.type === 'text';
      passIn.type = shown ? 'password' : 'text';
      eyeBtn.textContent = shown ? '👁' : '🙈';
    });

    // Form submission
    const form      = document.getElementById('loginForm');
    const loginBtn  = document.getElementById('loginBtn');
    const alertBox  = document.getElementById('alertBox');
    const userInput = document.getElementById('username');
    const userGroup = document.getElementById('userGroup');
    const userErr   = document.getElementById('userError');
    const passGroup = document.getElementById('passGroup');
    const passErr   = document.getElementById('passError');

    function clearErrors() {
      alertBox.textContent = '';
      alertBox.classList.remove('show');
      userGroup.classList.remove('error');
      userErr.textContent  = '';
      passGroup.classList.remove('error');
      passErr.textContent  = '';
    }

    function showAlert(msg) {
      alertBox.textContent = '⚠️  ' + msg;
      alertBox.classList.remove('show'); // reset animation
      void alertBox.offsetWidth;         // reflow to retrigger
      alertBox.classList.add('show');
    }

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clearErrors();

      const user = userInput.value.trim();
      const pass = passIn.value;
      let valid  = true;

      if (!user) {
        userGroup.classList.add('error');
        userErr.textContent = 'Username is required.';
        valid = false;
      }
      if (!pass) {
        passGroup.classList.add('error');
        passErr.textContent = 'Password is required.';
        valid = false;
      }
      if (!valid) return;

      // Loading state
      loginBtn.classList.add('loading');

      // Simulate async auth check (500ms)
      setTimeout(function () {
        loginBtn.classList.remove('loading');

        if (user === ADMIN_USER && pass === ADMIN_PASS) {
          // ── Successful login ────────────────────────────────────
          const remember = document.getElementById('rememberMe').checked;
          if (remember) {
            localStorage.setItem('sb-admin-auth', '1');
          } else {
            // sessionStorage only — clears on tab close
            sessionStorage.setItem('sb-admin-auth', '1');
            localStorage.removeItem('sb-admin-auth');
          }
          // Carry theme preference across to dashboard
          // (already stored in localStorage above)

          // Brief success flash before redirect
          loginBtn.style.background = 'linear-gradient(135deg,#2c9b71,#1e7050)';
          loginBtn.querySelector('.btn-text').textContent = '✓  Access Granted';
          setTimeout(function () {
            window.location.replace('index.html');
          }, 600);

        } else {
          // ── Failed login ────────────────────────────────────────
          if (user !== ADMIN_USER) {
            userGroup.classList.add('error');
            userErr.textContent = 'Unknown username.';
          } else {
            passGroup.classList.add('error');
            passErr.textContent = 'Incorrect password.';
          }
          showAlert('Invalid admin credentials. Please try again.');
          passIn.value = '';
          passIn.focus();
        }
      }, 520);
    });

    // Clear field errors on input
    userInput.addEventListener('input', function () {
      userGroup.classList.remove('error');
      userErr.textContent = '';
    });
    passIn.addEventListener('input', function () {
      passGroup.classList.remove('error');
      passErr.textContent = '';
    });
  });
})();
