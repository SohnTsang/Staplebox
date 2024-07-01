function showLoading() {
    document.getElementById('loadingSpinner').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingSpinner').style.display = 'none';
}


function hideSkeletonAndShowContent(skeletonId, contentId) {
    const loader = document.getElementById(skeletonId);
    const content = document.getElementById(contentId);
    if (loader && content) {
        // Hide skeleton and show content after a delay of 1 second
        setTimeout(() => {
            loader.style.display = 'none';  // Hide skeleton
            content.style.display = 'block';  // Show content
        }, 1000); // 1000 milliseconds = 1 second
    } else {
        console.log('Error: Element not found -', skeletonId, 'or', contentId);
    }
}

function toggleSkeletonVisibility(skeletonId, contentId, showSkeleton = false, includeImage = false) {
    const loader = document.getElementById(skeletonId);
    const content = document.getElementById(contentId);
    const skeletonImage = loader.querySelector('.skeleton-image');  // Find within loader context


    if (loader && content) {
        if (showSkeleton) {
            loader.style.display = 'block';
            content.style.display = 'none';
            // Decide whether to show or hide the skeleton image
            if (includeImage && skeletonImage) {
                skeletonImage.style.display = 'block';
            } else if (skeletonImage) {
                skeletonImage.style.display = 'none'; // Hide skeleton image on subsequent loads
            }
        } else {
            setTimeout(() => {
                loader.style.display = 'none';
                content.style.display = 'block';
                if (skeletonImage) {
                    skeletonImage.style.display = 'none'; // Always hide image after initial display
                }
            }, 1000);
        }
    } else {
        console.log('Error: Element not found -', skeletonId, 'or', contentId);
    }
}

function populateSkeletons(skeletonId, count, includeImage, initialLoad = false) {
    const container = document.getElementById(skeletonId);
    container.innerHTML = '';  // Clear previous contents if any

    // Fetch widths from data attribute and parse it as JSON
    const widths = JSON.parse(container.getAttribute('data-widths') || '{}');

    // Update container class based on whether it's the initial load
    if (initialLoad) {
        container.className = 'skeleton-list-center mt-3';  // Class for initial load
    } else {
        container.className = 'skeleton-list mt-3';  // Class for subsequent updates
    }

    if (includeImage) {
        container.innerHTML += `
            <div class="skeleton-list-item-center">
                <div class="skeleton-image"></div>
            </div>
        `;
    }
    for (let i = 0; i < count; i++) {
        let width = widths[i] || "100%";  // Use default width if not specified
        container.innerHTML += `
            <div class="${initialLoad ? 'skeleton-list-item-center' : 'skeleton-list-item'}">
                <div class="skeleton skeleton-text" style="width: ${width};"></div>
            </div>
        `;
    }
}
