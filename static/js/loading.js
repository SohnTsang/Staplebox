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

function toggleSkeletonVisibility(skeletonId, contentId, showSkeleton = false) {
  const loader = document.getElementById(skeletonId);
  const content = document.getElementById(contentId);

  if (loader && content) {
      if (showSkeleton) {
          // Show skeleton immediately and hide content
          loader.style.display = 'block';
          content.style.display = 'none';
      } else {
          // Hide skeleton and show content after a delay of 1 second
          setTimeout(() => {
              loader.style.display = 'none';
              content.style.display = 'block';
          }, 600); // Delay set to 1000 milliseconds = 1 second
      }
  } else {
      console.log('Error: Element not found -', skeletonId, 'or', contentId);
  }
}