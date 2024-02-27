$(document).ready(function() {
    // Use history.replaceState to avoid form resubmission dialog
    if (window.history.replaceState) {
        window.history.replaceState(null, null, window.location.href);
    }

    $('#loginForm, #signupForm').on('submit', function(e) {
        // Optionally prevent default submission for demonstration
        // e.preventDefault(); // Uncomment this during testing or if handling submission via AJAX

        var form = $(this);

        // Delay checking the form's validity to ensure it's done after native HTML5 validation

        // Clear previous submission flag
        localStorage.removeItem('formSubmitted');
        setTimeout(function() {
            var isValid = form[0].checkValidity();

            if (!isValid) {
                // This flag could be set when the form is submitted with errors
                localStorage.setItem('formSubmitted', 'true');
            } else {
                // Ensure flag is not set if form is valid
                localStorage.removeItem('formSubmitted');
            }
        }, 0);
    });

    // Check if there was a previous submission attempt that resulted in validation errors
    if (localStorage.getItem('formSubmitted') === 'true') {
        // Show only the first invalid feedback if there were validation errors on previous submission
        $(".invalid-feedback").hide(); // Ensure all are hidden first
        $(".invalid-feedback").first().attr('style', 'display: block !important');
        localStorage.removeItem('formSubmitted'); // Clear flag to avoid showing on subsequent reloads without errors
    }

    // Replace <strong> tags within errors, if necessary
});
