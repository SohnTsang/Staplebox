
    'show session message'
    document.addEventListener('DOMContentLoaded', function() {
        handleSessionMessage();  // Ensure this is called on page load
    });



    document.addEventListener('DOMContentLoaded', function () {
        const selectAllExports = document.getElementById('selectAllExports');
        const checkboxes = document.querySelectorAll('tbody input[type="checkbox"]');
        const bulkActionButton = document.getElementById('bulkActionButton');
        const bulkActionDropdown = document.getElementById('bulkActionDropdown');
        const bulkActionIcon = document.getElementById('bulkActionIcon');
        const deleteSelectedExports = document.getElementById('deleteSelectedExports');

        selectAllExports.addEventListener('change', function() {
            checkboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            toggleBulkActionButton();
        });

        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', toggleBulkActionButton);
        });

        function toggleBulkActionButton() {
            const anyChecked = Array.from(checkboxes).some(c => c.checked);
            bulkActionButton.disabled = !anyChecked;
            if (anyChecked) {
                bulkActionButton.classList.add('enabled');
                bulkActionButton.style.cursor = 'pointer';
            } else {
                bulkActionButton.classList.remove('enabled');
                bulkActionButton.style.cursor = 'initial';
            }
        }

        // Initial check to set the proper state of the bulk action button
        toggleBulkActionButton();  // Call this function on load to ensure correct initial state

        bulkActionButton.addEventListener('click', function(event) {
            event.preventDefault();
            if (!bulkActionButton.disabled) {
                bulkActionDropdown.classList.toggle('show');
                if (bulkActionDropdown.classList.contains('show')) {
                    bulkActionIcon.src = '/static/images/table_icon/arrow_drop_up_24dp_FILL0_wght400_GRAD0_opsz24_333333.png';
                } else {
                    bulkActionIcon.src = '/static/images/table_icon/arrow_drop_down_24dp_FILL0_wght400_GRAD0_opsz24_333333.png';
                }
            }
        });

        window.onclick = function(event) {
            if (!event.target.matches('.button-bulk-action') && !event.target.closest('.bulk-action-wrapper')) {
                if (bulkActionDropdown.classList.contains('show')) {
                    bulkActionDropdown.classList.remove('show');
                    bulkActionIcon.src = "{% static 'images/table_icon/arrow_drop_down_24dp_FILL0_wght400_GRAD0_opsz24_333333.png' %}";
                }
            }
        };

        deleteSelectedExports.addEventListener('click', function () {
            if (bulkActionButton.disabled) {
                return; // Prevent action if the button is disabled
            }

            const exportIds = Array.from(checkboxes)
                .filter(checkbox => checkbox.checked)
                .map(checkbox => checkbox.closest('tr').getAttribute('data-export-id'));

            if (confirm(`Are you sure you want to delete the selected exports?`)) {
                fetch(`/exports/delete/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ export_ids: exportIds })
                })
                .then(handleResponse)
                .catch(handleError);
            }
        });

        function handleResponse(response) {
            if (response.ok) {
                return response.json().then(data => {
                    setSessionMessage(data.message, 'success');
                    location.reload();
                });
            } else {
                throw new Error('Network response was not ok.');
            }
        }

        function handleError(error) {
            setSessionMessage('There was an error processing your request.', 'error');
            location.reload();
        }

        document.querySelectorAll('.icon-delete').forEach(icon => {
            icon.addEventListener('click', function () {
                const exportId = this.closest('tr').getAttribute('data-export-id');
                if (confirm('Are you sure you want to delete this export?')) {
                    fetch(`/exports/delete/`, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': getCookie('csrftoken'),
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ export_id: exportId })
                    })
                    .then(handleResponse)
                    .catch(handleError);
                }
            });
        });
    });

    'sort table by column'
    document.addEventListener('DOMContentLoaded', function() {
        const tableBody = document.getElementById('exportTableBody');
        const partnerNameHeader = document.getElementById('partnerNameHeader');
        const businessHeader = document.getElementById('businessHeader');
        const exportDateHeader = document.getElementById('exportDateHeader');

        let sortDirection = {
            partnerName: null,
            business: null,
            exportDate: 'asc'
        };

        function sortTable(column, type, header) {
            // Reset sort directions for all headers except the current one
            Object.keys(sortDirection).forEach(key => {
                if (key !== header.id) {
                    sortDirection[key] = null; // Reset other headers
                }
            });

            // If the current header has no sort direction set, initialize it
            if (!sortDirection[header.id]) {
                sortDirection[header.id] = type === 'string' ? 'asc' : 'desc';
            }

            const rows = Array.from(tableBody.querySelectorAll('tr'));
            let compareFunction;

            if (type === 'string') {
                compareFunction = (a, b) => {
                    const aText = a.querySelector(`td:nth-child(${column})`).textContent.trim();
                    const bText = b.querySelector(`td:nth-child(${column})`).textContent.trim();
                    return sortDirection[header.id] === 'asc' ? aText.localeCompare(bText) : bText.localeCompare(aText);
                };
            } else if (type === 'date') {
                compareFunction = (a, b) => {
                    const aDate = new Date(a.querySelector(`td:nth-child(${column})`).textContent.trim());
                    const bDate = new Date(b.querySelector(`td:nth-child(${column})`).textContent.trim());
                    return sortDirection[header.id] === 'desc' ? aDate - bDate : bDate - aDate;
                };
            }

            rows.sort(compareFunction);
            rows.forEach(row => tableBody.appendChild(row));

            // Toggle the current header's sort direction
            sortDirection[header.id] = sortDirection[header.id] === 'asc' ? 'desc' : 'asc';
            updateSortIcons(header.id);
        }

        function updateSortIcons(activeHeaderId) {
            // Only manage active/inactive states when a sort action is triggered
            document.querySelectorAll('.sort-icon').forEach(icon => {
                icon.classList.add('inactive');
                icon.classList.remove('active');
            });

            const activeIcon = document.querySelector(`#${activeHeaderId} .sort-icon`);
            activeIcon.classList.remove('inactive');
            activeIcon.classList.add('active');
            activeIcon.classList.toggle('asc', sortDirection[activeHeaderId] === 'asc');
            activeIcon.classList.toggle('desc', sortDirection[activeHeaderId] === 'desc');
        }


        partnerNameHeader.addEventListener('click', () => {
            sortTable(2, 'string', partnerNameHeader);
        });

        businessHeader.addEventListener('click', () => {
            sortTable(3, 'string', businessHeader);
        });

        exportDateHeader.addEventListener('click', () => {
            sortTable(4, 'date', exportDateHeader);
        });

        // Ensure the correct initial visibility and state of the sort icon
        updateSortIcons('exportDateHeader');
    });

    document.addEventListener('DOMContentLoaded', function () {
        const csrftoken = getCookie('csrftoken');
        let formData = new FormData();  // Initialize formData here to ensure it's accessible globally within this script
    
        var modal = document.getElementById('exportModal');
        var btn = document.getElementById('create_export_modal');
        var span = document.querySelector('.close');
        var cancelBtn = document.getElementById('cancelBtn');
        var addBtn = document.getElementById('addBtn');
        var partnersList = document.getElementById('partnersList');
        var addDateBtn = document.getElementById('addDateBtn');
        var datePicker = document.getElementById('datePicker');
        var uploadZone = document.getElementById('uploadZone');
        var uploadedFiles = document.getElementById('uploadedFiles');
        var exportDatesList = document.getElementById('exportDatesList');
        var selectedPartner = null;
        var selectedDates = []; // Store multiple dates
        let validFilesMap = new Map(); // Tracks valid files
        let invalidFileCount = 0; // Count of invalid files
    
        function updateUploadButtonState() {
            addBtn.disabled = invalidFileCount > 0;
        }
    
        function formatFileSize(sizeInBytes) {
            if (sizeInBytes < 1024) return "1 KB";
            let sizeInKb = sizeInBytes / 1024.0;
            const units = ['KB', 'MB', 'GB', 'TB', 'PB'];
            for (let unit of units) {
                if (sizeInKb < 1024.0) return `${sizeInKb.toFixed(1)} ${unit}`;
                sizeInKb /= 1024.0;
            }
            return `${sizeInKb.toFixed(1)} PB`;
        }
    
        function getFileTypeIcon(fileName) {
            const extension = fileName.split('.').pop().toLowerCase();
            const iconMap = {
                'png': '/static/images/table_icon/png.png',
                'csv': '/static/images/table_icon/csv.png',
                'zip': '/static/images/table_icon/zip.png',
                'jpg': '/static/images/table_icon/jpg.png',
                'pdf': '/static/images/table_icon/pdf.png',
                'doc': '/static/images/table_icon/doc.png',
                'docx': '/static/images/table_icon/doc.png',
                'xls': '/static/images/table_icon/xls.png',
                'xlsx': '/static/images/table_icon/xls.png',
                'xlsm': '/static/images/table_icon/xls.png',
                'ppt': '/static/images/table_icon/ppt.png',
                'txt': '/static/images/table_icon/txt.png',
                'default': '/static/images/table_icon/file.png'
            };
            return iconMap[extension] || iconMap['default'];
        }
    
        function loadPartners() {
            fetch('/exports/list_partners/')
                .then(response => response.json())
                .then(data => {
                    partnersList.innerHTML = '';
                    data.partners.forEach(partner => {
                        var li = document.createElement('li');
                        li.textContent = partner.partner_name;
                        li.setAttribute('data-partner', partner.id);  // Use partnership ID from the response
                        li.addEventListener('click', function() {
                            document.querySelectorAll('.partners-list li').forEach(item => {
                                item.classList.remove('selected');
                            });
                            li.classList.add('selected');
                            selectedPartner = partner.id;  // Correctly set selectedPartner
                        });
                        partnersList.appendChild(li);
                    });
                })
                .catch(error => {
                    console.error('Error loading partners:', error);
                });
        }
    
        if (btn) {
            btn.addEventListener('click', function() {
                formData = new FormData();
                modal.style.display = 'block';
                loadPartners();
            });
        }
    
        if (span) {
            span.addEventListener('click', function() {
                modal.style.display = 'none';
            });
        }
    
        if (cancelBtn) {
            cancelBtn.addEventListener('click', function() {
                modal.style.display = 'none';
        
                // Reset input fields in the modal
                var inputs = modal.querySelectorAll('input[type="text"], input[type="date"]');
                inputs.forEach(function(input) {
                    input.value = '';  // Reset text and date inputs
                });
        
                // Reset select elements
                var selects = modal.querySelectorAll('select');
                selects.forEach(function(select) {
                    select.selectedIndex = 0;  // Reset select to the first option
                });
        
                // Clear dynamic lists such as partners and dates
                partnersList.innerHTML = '';  // Clear the partners list
                exportDatesList.innerHTML = '';  // Clear the export dates list
        
                // Reset stored state variables
                selectedPartner = null;  // Clear selected partner
                selectedDates = [];  // Clear selected dates array
        
                // Clear uploaded files display and reset maps/counters
                uploadedFiles.innerHTML = '';  // Clear the list of uploaded files
                validFilesMap.clear();  // Clear the map of valid files
                invalidFileCount = 0;  // Reset the count of invalid files
        
                // Reset form data, if using it to track unsent changes
                formData = new FormData();  // Reinitialize formData
        
                // Optionally reset any error messages or visual feedback
                var errorMessages = modal.querySelectorAll('.error-message');
                errorMessages.forEach(function(message) {
                    message.style.display = 'none';  // Hide error messages
                });
        
                // Update UI elements if necessary
                updateUploadButtonState();
            });
        }
    
        var tabs = document.querySelectorAll('.tab');
        var tabContents = document.querySelectorAll('.tab-content');
        tabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                tabs.forEach(function(item) {
                    item.classList.remove('active');
                });
                tab.classList.add('active');
                var activeTab = tab.getAttribute('data-tab');
                tabContents.forEach(function(content) {
                    content.classList.remove('active');
                    if (content.id === activeTab) {
                        content.classList.add('active');
                    }
                });
            });
        });
    
        if (addDateBtn) {
            addDateBtn.addEventListener('click', function () {
                var input = datePicker.querySelector('input[type="date"]');
                var selectedDate = input.value;
                if (selectedDate) { // Check if the date input is not empty
                    selectedDates.push(selectedDate); // Add to selected dates
    
                    var li = document.createElement('li');
                    li.innerHTML = `<span>${selectedDate}</span> <button class="remove-date-btn">Remove</button>`;
                    exportDatesList.appendChild(li);
    
                    li.querySelector('.remove-date-btn').addEventListener('click', function () {
                        li.remove();
                        selectedDates = selectedDates.filter(date => date !== selectedDate); // Remove the date from selected dates
                    });
    
                    input.value = '';
                } else {
                    alert("Please select a date before adding.");
                }
            });
        }
    
        function setupFileHandlers() {
            uploadZone.addEventListener('click', function() {
                var fileInput = document.createElement('input');
                fileInput.type = 'file';
                fileInput.multiple = true;
                fileInput.style.display = 'none';
                fileInput.addEventListener('change', function() {
                    handleFiles(fileInput.files);
                });
                fileInput.click();
            });
    
            uploadZone.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.stopPropagation();
                uploadZone.classList.add('dragover');
            });
    
            uploadZone.addEventListener('dragleave', function(e) {
                e.preventDefault();
                e.stopPropagation();
                uploadZone.classList.remove('dragover');
            });
    
            uploadZone.addEventListener('drop', function(e) {
                e.preventDefault();
                e.stopPropagation();
                uploadZone.classList.remove('dragover');
                handleFiles(e.dataTransfer.files);
            });
        }
    
        function getFileTypeIcon(fileName) {
            const extension = fileName.split('.').pop().toLowerCase();
            const iconMap = {
                'png': '/static/images/table_icon/png.png',
                'csv': '/static/images/table_icon/csv.png',
                'zip': '/static/images/table_icon/zip.png',
                'jpg': '/static/images/table_icon/jpg.png',
                'pdf': '/static/images/table_icon/pdf.png',
                'doc': '/static/images/table_icon/doc.png',
                'docx': '/static/images/table_icon/doc.png',
                'xls': '/static/images/table_icon/xls.png',
                'xlsx': '/static/images/table_icon/xls.png',
                'xlsm': '/static/images/table_icon/xls.png',
                'ppt': '/static/images/table_icon/ppt.png',
                'txt': '/static/images/table_icon/txt.png',
                'default': '/static/images/table_icon/file.png'
            };
            return iconMap[extension] || iconMap['default'];
        }
    
        function handleFiles(files) {
            for (let i = 0; i < files.length; i++) {
                let file = files[i];
                let formattedSize = formatFileSize(file.size);
                let li = document.createElement('li');
                li.innerHTML = `<div class="file-info">
                                    <img src="${getFileTypeIcon(file.name)}" alt="${file.name.split('.').pop()}" class="file-icon">
                                    <span class="file-name">${file.name}</span>
                                    <span class="file-size">${formattedSize}</span>
                                    <button class="remove-document-btn">Delete</button>
                                </div>
                                <progress class="upload-progress" value="0" max="100"></progress>`;
                uploadedFiles.appendChild(li);
    
                const progressBar = li.querySelector('.upload-progress');
                if (file.size <= 10 * 1024 * 1024) {
                    validFilesMap.set(file, li);
                    formData.append('documents', file); // Append each valid file to the formData object
                } else {
                    li.style.border = "1px solid red";
                    li.style.backgroundColor = "#ffcccc88";
                    invalidFileCount++; // Increment invalid file count
                }
    
                let reader = new FileReader();
                reader.onload = () => {
                    progressBar.value = 100;
                    progressBar.style.background = "linear-gradient(to right, #4caf50 100%, #f3f3f3 0%)";
                };
                reader.readAsDataURL(file);
    
                li.querySelector('.remove-document-btn').addEventListener('click', () => {
                    if (file.size > 10 * 1024 * 1024) {
                        invalidFileCount--; // Decrement invalid file count
                    } else {
                        validFilesMap.delete(file);
                        formData.delete('documents', file); // Remove the file from formData when it's deleted from the UI
                    }
                    uploadedFiles.removeChild(li);
                    updateUploadButtonState();
                });
            }
            updateUploadButtonState();
        }
    
        addBtn.addEventListener('click', function () {
            let valid = true;
            let messageShown = false;
            
            formData.delete('partner');
            formData.delete('export_dates[]');
        
            if (selectedPartner) {
                formData.append('partner', selectedPartner);
            } else {
                if (!messageShown) {
                    showMessage('Please select a partner.', 'error');
                    messageShown = true;
                }
                valid = false;
            }
        
            if (selectedDates.length > 0) {
                selectedDates.forEach(date => formData.append('export_dates[]', date)); // Append all selected dates
            } else {
                if (!messageShown) {
                    showMessage('Please select at least one export date.', 'error');
                    messageShown = true;
                }
                valid = false;
            }
        
            if (!valid) {
                return; // Do not proceed with the fetch if the form is invalid
            }
        
            fetch('/exports/create/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrftoken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.errors) {
                    if (!messageShown) {
                        showMessage('There was an error processing your request.', 'error');
                        messageShown = true;
                    }
                } else {
                    setSessionMessage(data.message, 'success');
                    location.reload();
                }
            })
            .catch(error => {
                console.error('Error creating export:', error);
                if (!messageShown) {
                    showMessage('There was an error processing your request.', 'error');
                    messageShown = true;
                }
            });
        });
        setupFileHandlers();
    });
    
    