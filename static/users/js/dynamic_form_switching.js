document.addEventListener("DOMContentLoaded", function() {
    // Show the JavaScript-dependent links when JavaScript is enabled
    var jsLoginLink = document.getElementById("js-enabled-login-link");
    var jsSignupLink = document.getElementById("js-enabled-signup-link");

    if (jsLoginLink) {
        jsLoginLink.style.display = 'inline'; // Or any other style changes you want
    }

    if (jsSignupLink) {
        jsSignupLink.style.display = 'inline'; // Or any other style changes you want
    }
    document.querySelectorAll('.switch-form').forEach(function(link) {
        if (link.id.endsWith("-js")) { // Identify JS-dependent links by their ID suffix
            link.style.display = ''; // Remove the inline style to show them
        }
    });
});

document.addEventListener("DOMContentLoaded", function() {
    var showSignupBtn = document.getElementById("js-enabled-login-link");
    var showLoginBtn = document.getElementById("js-enabled-signup-link");

    // Show Signup Form and Change URL
    if (showSignupBtn) {
        showSignupBtn.addEventListener("click", function() {
            // Change the URL to the signup page
            history.pushState({page: "signup"}, "Signup", "/accounts/signup/");
            // Here you would also add your logic to display the signup form
        });
    }

    // Show Login Form and Change URL
    if (showLoginBtn) {
        showLoginBtn.addEventListener("click", function() {
            // Change the URL to the login page
            history.pushState({page: "login"}, "Login", "/accounts/login/");
            // Here you would also add your logic to display the login form
        });
    }

    // Handle browser back button to toggle between forms correctly
    window.addEventListener("popstate", function(event) {
        if (event.state && event.state.page) {
            if (event.state.page === "signup") {
                // Show signup form
            } else if (event.state.page === "login") {
                // Show login form
            }
        }
    });
});
