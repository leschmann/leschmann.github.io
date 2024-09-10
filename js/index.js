// Function to calculate and set animation speed based on viewport size
function setAnimationSpeed() {
    // Get viewport width and height
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    // Calculate animation duration based on viewport dimensions
    // (Here, we use an example formula. You can adjust it as needed.)
    const animationDuration = viewportWidth / 100; // Example: 1 second per 100px of viewport size

    // Select the element with the class "header-wrap"
    const headerWrap = document.querySelector('.header-wrap');

    if (headerWrap) {
        // Update the animation duration in seconds
        headerWrap.style.animationDuration = animationDuration + 's';
    }

    console.log(`Animation duration set to: ${animationDuration}s`);
}

// Call the function on initial load
setAnimationSpeed();

// Call the function on window resize
window.addEventListener('resize', setAnimationSpeed);
