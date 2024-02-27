

document.addEventListener("DOMContentLoaded", function() {
    var passwordInput = document.querySelector('input[name="password1"]');
    var progressBar = document.querySelector('#passwordStrength .progress-bar');

    passwordInput.addEventListener('input', function() {
        var passwordStrength = zxcvbn(passwordInput.value);
        var percent = passwordStrength.score * 25; // zxcvbn score is 0-4

        progressBar.style.width = percent + '%';
        progressBar.classList.remove('bg-danger', 'bg-warning', 'bg-info', 'bg-success');

        if (percent === 0) {
            progressBar.classList.add('bg-danger');
        } else if (percent <= 25) {
            progressBar.classList.add('bg-danger');
        } else if (percent <= 50) {
            progressBar.classList.add('bg-warning');
        } else if (percent <= 75) {
            progressBar.classList.add('bg-info');
        } else {
            progressBar.classList.add('bg-success');
        }
    });
});