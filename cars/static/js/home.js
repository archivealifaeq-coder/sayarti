(function() {
    'use strict';
    
    // ============================================ //
    //  NAVBAR SCROLL EFFECT                        //
    // ============================================ //
    var navbar = document.getElementById('navbar');
    var scrollTimeout;
    
    window.addEventListener('scroll', function() {
        if (scrollTimeout) window.cancelAnimationFrame(scrollTimeout);
        scrollTimeout = window.requestAnimationFrame(function() {
            var scrollY = window.scrollY || window.pageYOffset;
            navbar.classList.toggle('scrolled', scrollY > 50);
        });
    }, { passive: true });
    
    // ============================================ //
    //  TICKER DUPLICATION FOR INFINITE SCROLL     //
    // ============================================ //
    var tickerTrack = document.getElementById('tickerTrack');
    if (tickerTrack) {
        var items = tickerTrack.querySelectorAll('.ticker-item');
        if (items.length > 0 && items.length < 10) {
            var cloned = [];
            items.forEach(function(item) {
                var clone = item.cloneNode(true);
                cloned.push(clone);
            });
            cloned.forEach(function(clone) {
                tickerTrack.appendChild(clone);
            });
        }
    }
    
    // ============================================ //
    //  MAIN SLIDER                                //
    // ============================================ //
    var mainTrack = document.getElementById('sliderMainTrack');
    var mainSlides = mainTrack ? mainTrack.querySelectorAll('.slider-main-slide') : [];
    var mainDots = document.querySelectorAll('.slider-main-dot');
    var mainPrevBtn = document.getElementById('sliderMainPrev');
    var mainNextBtn = document.getElementById('sliderMainNext');
    var mainIndex = 0;
    var mainCount = mainSlides.length;
    var mainInterval = null;
    var mainTransitioning = false;
    
    if (mainCount > 0) {
        updateMainSlider(0, false);
        if (mainCount > 1) startMainAutoPlay();
        
        function updateMainSlider(index, animate) {
            if (mainTransitioning) return;
            if (animate === undefined) animate = true;
            if (index < 0) index = mainCount - 1;
            if (index >= mainCount) index = 0;
            if (index === mainIndex && animate !== false) return;
            
            mainTransitioning = true;
            mainIndex = index;
            
            if (mainTrack) {
                mainTrack.style.transition = animate ? 'transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)' : 'none';
                mainTrack.style.transform = 'translateX(-' + (mainIndex * 100) + '%)';
            }
            
            mainDots.forEach(function(dot, i) {
                dot.classList.toggle('active', i === mainIndex);
            });
            
            setTimeout(function() { mainTransitioning = false; }, 850);
        }
        
        function nextMainSlide() {
            if (mainCount > 1) updateMainSlider(mainIndex + 1);
        }
        
        function prevMainSlide() {
            if (mainCount > 1) updateMainSlider(mainIndex - 1);
        }
        
        function startMainAutoPlay() {
            if (mainInterval) clearInterval(mainInterval);
            mainInterval = setInterval(nextMainSlide, 5000);
        }
        
        function resetMainAutoPlay() {
            if (mainInterval) {
                clearInterval(mainInterval);
                mainInterval = null;
            }
            startMainAutoPlay();
        }
        
        if (mainPrevBtn) {
            mainPrevBtn.addEventListener('click', function(e) {
                e.preventDefault();
                resetMainAutoPlay();
                prevMainSlide();
            });
        }
        
        if (mainNextBtn) {
            mainNextBtn.addEventListener('click', function(e) {
                e.preventDefault();
                resetMainAutoPlay();
                nextMainSlide();
            });
        }
        
        mainDots.forEach(function(dot, index) {
            dot.addEventListener('click', function(e) {
                e.preventDefault();
                if (index !== mainIndex) {
                    resetMainAutoPlay();
                    updateMainSlider(index);
                }
            });
        });
        
        var mainContainer = document.querySelector('.slider-main-container');
        if (mainContainer) {
            mainContainer.addEventListener('mouseenter', function() {
                if (mainInterval) {
                    clearInterval(mainInterval);
                    mainInterval = null;
                }
            });
            
            mainContainer.addEventListener('mouseleave', function() {
                if (mainCount > 1 && !mainInterval) startMainAutoPlay();
            });
            
            // Touch support for mobile
            var touchStartX = 0;
            var touchStartY = 0;
            
            mainContainer.addEventListener('touchstart', function(e) {
                touchStartX = e.changedTouches[0].screenX;
                touchStartY = e.changedTouches[0].screenY;
            }, { passive: true });
            
            mainContainer.addEventListener('touchend', function(e) {
                var diffX = touchStartX - e.changedTouches[0].screenX;
                var diffY = touchStartY - e.changedTouches[0].screenY;
                if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 30) {
                    resetMainAutoPlay();
                    if (diffX > 0) nextMainSlide();
                    else prevMainSlide();
                }
            }, { passive: true });
        }
    }
    
    // ============================================ //
    //  MOBILE MENU TOGGLE                         //
    // ============================================ //
    var menuToggle = document.getElementById('menuToggle');
    if (menuToggle) {
        var navMenu = document.querySelector('.hidden.md\\:flex');
        var isMenuOpen = false;
        
        menuToggle.addEventListener('click', function() {
            isMenuOpen = !isMenuOpen;
            if (isMenuOpen) {
                navMenu.classList.remove('hidden');
                navMenu.classList.add('flex', 'flex-col', 'absolute', 'top-full', 'left-0', 'right-0', 'bg-slate-900/95', 'p-6', 'backdrop-blur', 'rounded-b-2xl', 'border-t', 'border-amber-500/10', 'gap-4');
                menuToggle.setAttribute('aria-expanded', 'true');
                menuToggle.textContent = '✕';
            } else {
                navMenu.classList.add('hidden');
                navMenu.classList.remove('flex', 'flex-col', 'absolute', 'top-full', 'left-0', 'right-0', 'bg-slate-900/95', 'p-6', 'backdrop-blur', 'rounded-b-2xl', 'border-t', 'border-amber-500/10', 'gap-4');
                menuToggle.setAttribute('aria-expanded', 'false');
                menuToggle.textContent = '☰';
            }
        });
    }
    
    // ============================================ //
    //  HTMX SUGGESTIONS HANDLER                   //
    // ============================================ //
    document.addEventListener('htmx:afterSwap', function(evt) {
        if (evt.target && evt.target.id === 'suggestions-container') {
            try {
                var data = JSON.parse(evt.detail.xhr.responseText);
                var modelList = document.getElementById('model-list');
                var engineList = document.getElementById('engine-list');
                
                if (data.models && data.models.length > 0) {
                    modelList.innerHTML = '';
                    data.models.forEach(function(model) {
                        var option = document.createElement('option');
                        option.value = model;
                        modelList.appendChild(option);
                    });
                } else {
                    modelList.innerHTML = '';
                }
                
                if (data.engines && data.engines.length > 0) {
                    engineList.innerHTML = '';
                    data.engines.forEach(function(engine) {
                        var option = document.createElement('option');
                        option.value = engine;
                        engineList.appendChild(option);
                    });
                } else {
                    engineList.innerHTML = '';
                }
            } catch (err) {
                // Silently fail
            }
        }
    });
    
    // ============================================ //
    //  SEARCH SCROLL BEHAVIOR                     //
    // ============================================ //
    var carsContainer = document.getElementById('cars-container');
    var searchButton = document.getElementById('searchButton');
    var searchForm = document.getElementById('searchForm');
    var isSearching = false;
    
    // Prevent focus issues with datalist
    var searchInputs = document.querySelectorAll('.search-input');
    searchInputs.forEach(function(input) {
        input.addEventListener('focus', function(e) {
            e.stopPropagation();
        });
        input.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    });
    
    if (searchButton) {
        searchButton.addEventListener('click', function(e) {
            isSearching = true;
            setTimeout(function() {
                if (carsContainer) {
                    carsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 200);
        });
    }
    
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            isSearching = true;
            setTimeout(function() {
                if (carsContainer) {
                    carsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 250);
        });
    }
    
    document.addEventListener('htmx:afterRequest', function(evt) {
        if (evt.target && evt.target.closest('form') && isSearching) {
            setTimeout(function() {
                if (carsContainer) {
                    var hasResults = carsContainer.querySelector('.car-card') !== null;
                    var hasNoResults = carsContainer.querySelector('.text-center.py-10') !== null;
                    if (hasResults || hasNoResults) {
                        carsContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
                isSearching = false;
            }, 400);
        }
    });
    
    // ============================================ //
    //  KEYBOARD SHORTCUTS                         //
    // ============================================ //
    document.addEventListener('keydown', function(e) {
        // Ctrl+K or Cmd+K to focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            var searchInput = document.querySelector('.search-input');
            if (searchInput) searchInput.focus();
        }
        // Escape to blur search
        if (e.key === 'Escape') {
            var activeElement = document.activeElement;
            if (activeElement && activeElement.classList.contains('search-input')) {
                activeElement.blur();
            }
        }
    });
    
    console.log('🚗 سيارتي - تم تحميل الصفحة بنجاح ✨');
    
})();