
document.addEventListener('DOMContentLoaded', function() {

    const explorerElement = document.getElementById('product-explorer');
    const rootFolderId = explorerElement.getAttribute('data-root-folder-id'); // Fetch the root folder ID
    const productId = document.querySelector('[data-product-id]').getAttribute('data-product-id');

    let currentFolderId = new URLSearchParams(window.location.search).get('folderId') || rootFolderId;


    const createFolderModal = new bootstrap.Modal(document.getElementById('createFolderModal'));
    const createFolderForm = document.getElementById('create-folder-form-modal');

    const uploadDocumentModal = new bootstrap.Modal(document.getElementById('uploadDocumentModal'));

    createFolderForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        const folderName = document.getElementById('folderName').value; // Assuming 'folderName' is the ID of your input field for the folder name
        const productId = document.getElementById('product-explorer').dataset.productId;

        formData.append('product', productId);
        if (currentFolderId) {
            formData.append('parent_id', currentFolderId);
        }

        const jsonSubmit = document.getElementById('jsonSubmit').checked;

        console.log(jsonSubmit, 123);

        if (jsonSubmit) {
            const jsonData = {};
            formData.forEach((value, key) => {
                jsonData[key] = value;
            });
    
            fetch(`/products/${productId}/explorer/create_folder/`, {
                method: 'POST',
                body: JSON.stringify(jsonData),
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                },
                credentials: 'include',
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    $('#createFolderModal').modal('hide').on('hidden.bs.modal', function () {
                        $(".modal-backdrop").remove();
                    });
                    createFolderModal.hide();
                    fetchFolderContents(parentFolderId); // Optionally, refresh the folder list
                } else {
                    console.error('Error creating folder:', data.errors);
                }
            })
            .catch(error => console.error('Error:', error));
        } else {
            this.submit();
        }
    });

    
    function navigateToFolder(folderId) {

        const productId = document.getElementById('product-explorer').getAttribute('data-product-id');

        // Update the URL with the new folder ID without reloading the page
        const newUrl = `/products/${productId}/explorer/?folderId=${folderId}`;
        history.pushState({ folderId: folderId }, '', newUrl);

        // Fetch the folder contents
        fetch(`/products/${productId}/explorer/folder/${folderId}/`, {
            method: 'GET',
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(response => response.json())
        .then(data => {
            updateFolderContents(data, currentFolderId);
            updateBreadcrumbs(data.breadcrumbs, data.currentFolderName, productId);

        });
        // Update the current folder ID
        currentFolderId = folderId;
    }


    function updateFolderContents(data, folderId) {
        const folderContainer = document.getElementById('folder-contents');
        folderContainer.innerHTML = ''; // Clear existing content

        const docListContainer = document.createElement('div');
        docListContainer.id = `document-list-${folderId}`;
        docListContainer.className = 'document-list';
        folderContainer.appendChild(docListContainer);

        // Dynamically create and add folder items to the container
        data.folders.forEach(folder => {
            const folderElement = document.createElement('div');
            folderElement.className = 'folder-item';
            folderElement.innerHTML = `
                <a href="#" class="folder-link" data-folder-id="${folder.id}">${folder.name}</a>
                <button class="btn btn-danger btn-sm delete-folder-btn" data-folder-id="${folder.id}">Delete</button>
            `;
            folderContainer.appendChild(folderElement);
        });

        // Bind event listeners to the new folder links and delete buttons
        bindBreadcrumbEventListeners();
        bindDeleteFolderEvents(); // Assuming you have a function for handling delete button clicks
        updateDocumentList(data.documents, folderId);
    }

    function bindBreadcrumbEventListeners() {
        // Bind click events to both folder items and breadcrumb links
        document.querySelectorAll('.folder-item .folder-link, #breadcrumbs a[data-folder-id]').forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault(); // Prevent default anchor action
                const folderId = this.dataset.folderId || this.getAttribute('data-folder-id');
                navigateToFolder(folderId);


                // Update the URL to reflect the current folder, if necessary
                window.history.pushState(null, '', `/products/${productId}/explorer/?folderId=${folderId}`);
            });
        });
    }

    function bindDeleteFolderEvents() {
        document.querySelectorAll('.delete-folder-btn').forEach(button => {
            button.addEventListener('click', function(e) {
                e.preventDefault();
                const folderId = this.getAttribute('data-folder-id');
                // Confirmation dialog
                if (confirm("Are you sure you want to delete this folder? This action cannot be undone.")) {
                    const csrfToken = getCookie('csrftoken');
                    fetch(`/folder/delete/${folderId}/`, {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrfToken,
                        },
                        credentials: 'include',
                    })
                    .then(response => response.json())
                    .then(data => {
                        if(data.success) {
                            // Remove the folder element from the DOM
                            this.parentElement.remove();
                            // Optionally, check if there are no more folders and update UI accordingly
                        } else {
                            alert("Error deleting folder.");
                        }
                    })
                    .catch(error => console.error('Error deleting folder:', error));
                }
            });
        });
    }

    // Function to navigate to a folder and update content and breadcrumbs
    function updateBreadcrumbs(breadcrumbs, currentFolderName, productId) {
        const breadcrumbContainer = document.getElementById('breadcrumbs');
        breadcrumbContainer.innerHTML = ''; // Start fresh each time


        if (currentFolderName === 'Root' || currentFolderId === rootFolderId) {
        // For the root folder, display a non-clickable "Root" breadcrumb
            breadcrumbContainer.innerHTML += `<li class="breadcrumb-item">Root</li>`;
        } else {
            // For non-root folders, add a clickable "Root" breadcrumb
            breadcrumbContainer.innerHTML += `<li class="breadcrumb-item">
                <a href="#" class="breadcrumb-link" data-folder-id="${rootFolderId}">Root</a>

            </li>`;
        }

        breadcrumbs.forEach((b, index) => {
        // Skip adding "Root" if it's part of the breadcrumbs array
        if (b.name === "Root" && index === 0) return;

            const breadcrumbHTML = `<li class="breadcrumb-item ${b.id === currentFolderId ? 'active' : ''}">
                <a href="#" class="breadcrumb-link" data-folder-id="${b.id}">${b.name}</a>
            </li>`;
            breadcrumbContainer.innerHTML += breadcrumbHTML;
        });

        // Add current folder as the last breadcrumb, if not "Root"
        if (currentFolderName && currentFolderName !== "Root") {
            breadcrumbContainer.innerHTML += `<li class="breadcrumb-item active" aria-current="page">${currentFolderName}</li>`;
        }

        const breadcrumbLinks = breadcrumbContainer.querySelectorAll('.breadcrumb-link');
        breadcrumbLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const folderId = this.getAttribute('data-folder-id');
                navigateToFolder(folderId); // Assuming navigateToFolder is correctly attached to window
            });
        });
    }

    function showLoadingIndicator(show) {
        document.getElementById('loadingIndicator').style.display = show ? 'block' : 'none';
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }


    fetchFolderContents(currentFolderId);


    //Delete folder button
    document.querySelectorAll('.delete-folder-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const folderId = this.getAttribute('data-folder-id');
            // Confirmation dialog
            if (confirm("Are you sure you want to delete this folder? This action cannot be undone.")) {
                const csrfToken = getCookie('csrftoken');
                fetch(`/folder/delete/${folderId}/`, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken,
                    },
                    credentials: 'include',
                })
                .then(response => response.json())
                .then(data => {
                    if(data.success) {
                        // Remove the folder element from the DOM
                        document.querySelector(`div[data-folder-id="${folderId}"]`).remove();
                        // Check if there are no more folders
                        if (document.querySelectorAll('.folder-item').length === 0) {
                            // Display "No folders found" message
                            document.getElementById('no-folders-message').style.display = 'block';
                        }
                    } else {
                        alert("Error deleting folder.");
                    }
                })
                .catch(error => console.error('Error:', error));
            }
        });
    });


    function fetchFolderContents(folderId) {
        // Determine the URL based on whether we're fetching the root folder or a specific folder
        let url = `/products/${productId}/explorer/`;
        if (folderId && folderId !== 'root') {
            url += `folder/${folderId}/`;  // Adjust as needed based on your backend's URL scheme
        }

        fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'include',  // If needed for session management
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            updateFolderContents(data, currentFolderId);  // Update your UI with the fetched data

            updateDocumentList(data.documents, folderId);
            updateBreadcrumbs(data.breadcrumbs, data.currentFolderName, productId);
        })
        .catch(error => {
            console.error('Error fetching folder contents:', error);
        });
    }


    function updateDocumentList(documents, folderId) {
        // Assuming you have the correct endpoint to fetch documents by folderId

        fetch(`/products/${productId}/folders/${folderId}/documents/`)
            .then(response => response.json())
            .then(data => {
                const documents = data.documents;
                let docListContainer = document.getElementById(`document-list-${folderId}`);
                if (!docListContainer) {
                    const folderContentsContainer = document.getElementById('folder-contents');
                    docListContainer = document.createElement('div');
                    docListContainer.id = `document-list-${folderId}`;
                    docListContainer.className = 'document-list';
                    folderContentsContainer.appendChild(docListContainer);
                } else {
                    // Clear existing content if the container already exists
                    docListContainer.innerHTML = '';
                }
                // Iterate over the documents to append each to the document list container
                documents.forEach(documentData => appendDocumentToFolder(documentData, folderId));
            })
            .catch(error => console.error('Error fetching documents:', error));
    }

    function appendDocumentToFolder(documentData, folderId) {
        const docListId = `document-list-${folderId}`;  // Dynamic ID based on folder
        const docList = document.getElementById(docListId);

        if (!docList) {
            console.error('Document list container not found for folder ID:', folderId);
            return;
        }

        // Create the container for the new document
        const docItem = document.createElement('div');
        docItem.className = 'document-item';
        docItem.setAttribute('data-document-id', documentData.id);

        // Create the document details element
        const docDetails = document.createElement('div');
        docDetails.innerHTML = `
            <span>${documentData.name}</span> |
            <span>Type: ${documentData.document_type}</span> |
            <span>Size: ${formatBytes(documentData.size)}</span> |
            <span>Uploaded: ${documentData.uploaded_at}</span>
            <a href="/documents/download/${documentData.id}/" target="_blank">Download</a>
        `;

        docItem.appendChild(docDetails);

        // Create and append the delete button
        const deleteBtn = createDeleteButton(documentData.id);
        docItem.appendChild(deleteBtn);

        // Append the document item to the document list in the UI
        docList.appendChild(docItem);
    }

    function createDeleteButton(documentId) {
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn btn-danger btn-sm delete-document-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.setAttribute('data-document-id', documentId);
        deleteBtn.onclick = () => deleteDocument(documentId);
        return deleteBtn;
    }

    function deleteDocument(documentId) {
        // Implement the logic to delete the document
        // Similar to the document upload, but call the endpoint for document deletion
        // After successful deletion, remove the document item from the UI
        fetch(`/documents/delete/${documentId}/`, {
        // fetch(`/folder/delete/${folderId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'include',
        })
        .then(response => response.json())
        .then(data => {
            if(data.success) {
                // Attempt to find and remove the document from the UI
                const documentElement = document.querySelector(`div[data-document-id="${documentId}"]`);
                if (documentElement) {
                    documentElement.remove();
                } else {
                    console.error('Document element not found for ID:', documentId);
                }
            } else {
                console.error('Error deleting document:', data.errors);
            }
        })
        .catch(error => console.error('Error:', error));
    }

    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }


    document.getElementById('upload-document-form').addEventListener('submit', function(e) {
        e.preventDefault();
        const formData = new FormData(this);
        formData.append('folder_id', currentFolderId); // Ensure currentFolderId is kept updated as you navigate

        const files = document.getElementById('documentFile').files;
        const documentTypeSelect = document.getElementById('documentType').value;
        const selectedDocumentTypeId = documentTypeSelect.value;


        Array.from(files).forEach((file, index) => {
            formData.append(`file_${index}`, file); // Append file
            const documentTypeId = document.querySelector(`[name="document_type_${index}"]`).value; // Get the selected document type for this file
            formData.append(`document_type_${index}`, documentTypeId); // Append document type ID
        });

        formData.append('folder_id', currentFolderId);


        fetch(`/products/${productId}/folders/${currentFolderId}/upload_document/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'include',
        })
        .then(response => response.json())
        .then(data => {
            if(data.success) {
                // Handle success, e.g., append the new document to the DOM.
                
                $('#uploadDocumentModal').modal('hide').on('hidden.bs.modal', function () {
                    // Check if a backdrop remains and remove it
                    $(".modal-backdrop").remove(); // For Bootstrap 5
                });
                uploadDocumentModal.hide();
                data.documents.forEach(document => appendDocumentToFolder(document, currentFolderId));

            } else {
                // Handle error
                console.error('Error uploading document:', data.errors);
            }
        })
        .catch(error => console.error('Error:', error));
    });

});

document.addEventListener('DOMContentLoaded', function() {
    // Fetch document types and store them

    let currentFolderId = new URLSearchParams(window.location.search).get('folderId') || rootFolderId;
    const productId = document.querySelector('[data-product-id]').getAttribute('data-product-id');
    let documentTypes = [];

    fetch(`/products/${productId}/folders/${currentFolderId}/api/document_types/`)  // Adjust the URL based on your actual endpoint
      .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        documentTypes = data; // Adjust based on your actual response structure

        updateDocumentTypeOptions();
      });

    document.getElementById('documentFile').addEventListener('change', function(e) {
        const files = e.target.files;
        const formContainer = document.getElementById('dynamicFormsContainer'); // Container in your modal

        // Clear previous inputs
        formContainer.innerHTML = '';

        Array.from(files).forEach((file, index) => {


            const formGroup = document.createElement('div');
            formGroup.className = 'form-group';
            let optionsHtml = '';
            if (documentTypes && documentTypes.length > 0) {

                optionsHtml = documentTypes.map(type => `<option value="${type.id}">${type.type_name}</option>`).join('');
            } else {
                console.error('Document types not loaded correctly.');
            }

            formGroup.innerHTML = `
                <label>Document Type for ${file.name}:</label>
                <select class="form-control" name="document_type_${index}" id="documentType">
                    ${optionsHtml}
                </select>
            `;
            formContainer.appendChild(formGroup);
        });
    });

    function updateDocumentTypeOptions() {
    // Assuming 'documentTypes' is an array of document type objects available globally
        const documentTypeSelects = document.querySelectorAll('.document-type-select'); // This class should be added to your dynamically created selects

        // Clear existing options in each select (optional)
        documentTypeSelects.forEach(select => {
            select.innerHTML = ''; // Clear existing options
            // Populate each select with new options
            documentTypes.forEach(type => {
                const option = document.createElement('option');
                option.value = type.id;
                option.textContent = type.type_name;
                select.appendChild(option);
            });
        });
    }

});