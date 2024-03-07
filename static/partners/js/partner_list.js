

document.addEventListener('DOMContentLoaded', function() {
    // Function to hide messages after 3 seconds
    setTimeout(function() {
        var messages = document.querySelectorAll('#alert-message, #success-message');
        messages.forEach(function(message) {
            message.style.display = 'none';
        });
    }, 3000); // 3000 milliseconds = 3 seconds
});
document.addEventListener('DOMContentLoaded', function() {
    // Event listener for deleting partners
    document.querySelectorAll('#delete-partner').forEach(button => {
        button.addEventListener('click', function() {
            const partnerId = this.getAttribute('data-partner-id');
            if(partnerId) {
                deleteEntity('partner', partnerId);
                window.location.reload();
            }
        });
    });

    // Event listener for deleting invitations
    document.querySelectorAll('#delete-invitation').forEach(button => { // Assuming a class for invitation delete buttons
        button.addEventListener('click', function() {
            const invitationId = this.getAttribute('data-invitation-id');
            if(invitationId) {
                deleteEntity('invitation', invitationId);
            }
        });
    });
});

// Unified delete function for both partners and invitations
function deleteEntity(entityType, entityId) {
    let confirmMessage = entityType === 'partner' 
        ? 'Are you sure you want to delete this partner? This action cannot be undone.' 
        : 'Are you sure you want to delete this invitation? This action cannot be undone.';
    let deleteUrl = entityType === 'partner' 
        ? `/partners/delete/${entityId}/` 
        : `/invitations/delete/${entityId}/`;

    if (!confirm(confirmMessage)) {
        return; // Early return if the user cancels the confirmation
    }

    fetch(deleteUrl, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken(),
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok.');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            const elementId = entityType === 'partner' ? `partner-${entityId}` : `invitation-${entityId}`;
            const element = document.getElementById(elementId);
            if (element) element.remove();
        } else {
            alert(`Error deleting ${entityType}.`);
        }
    })
    .catch(error => console.error('Error:', error));
}

// Function to get CSRF token from the cookie
function getCSRFToken() {
    let csrfToken = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 10) === ('csrftoken=')) {
                csrfToken = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }
    return csrfToken;
}

