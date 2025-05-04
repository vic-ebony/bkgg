// --- Helper functions (moved from inline script) ---
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

function escapeHtml(unsafe) {
    if (unsafe === null || unsafe === undefined) return '';
    return String(unsafe)
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// --- Read Django Context ---
let DJANGO_CONTEXT = {};
try {
    const contextElement = document.getElementById('django-context');
    if (contextElement) {
        DJANGO_CONTEXT = JSON.parse(contextElement.textContent);
    } else {
        console.error("Django context script tag not found!");
    }
} catch (e) {
    console.error("Error parsing Django context:", e);
}

const USER_ID = DJANGO_CONTEXT.userId || null;
const csrfToken = DJANGO_CONTEXT.csrfToken || getCookie('csrftoken'); // Fallback if needed
const URLS = DJANGO_CONTEXT.urls || {}; // Access URLs like URLS.add_pending
const isLoggedIn = DJANGO_CONTEXT.isLoggedIn || false; // Get boolean directly

// --- Main Application Logic ---
document.addEventListener('DOMContentLoaded', function() {
    const bottomOverlay = document.getElementById('bottomOverlay');
    // const isLoggedIn = USER_ID !== null; // Now using DJANGO_CONTEXT.isLoggedIn

    // --- decodeUnicodeEscapes function ---
    function decodeUnicodeEscapes(text) {
        if (typeof text !== 'string') { return text; }
        try {
            // Improved regex to handle potential issues
            return text.replace(/\\u([\dA-Fa-f]{4})/g, (match, hex) => {
                return String.fromCharCode(parseInt(hex, 16));
            });
        } catch (e) {
            console.error("Error decoding unicode escapes:", e);
            return text; // Return original text on error
        }
    }

    // --- updateRowsByAnimalId function ---
    function updateRowsByAnimalId(animalId, updateCallback) {
        // Ensure animalId is treated as a string for consistent attribute matching
        const rows = document.querySelectorAll(`.body-table tr[data-animal-id="${String(animalId)}"]:not(.note-row)`);
        rows.forEach(row => updateCallback(row));
    }

    // --- showPlusDropdown function ---
    function showPlusDropdown(triggerBtn) {
        const dropdown = document.getElementById('plusDropdown');
        if (!dropdown) return;
        dropdown.innerHTML = ""; // Clear previous items
        const row = triggerBtn.closest('tr');
        if (!row) return;
        const animalId = row.getAttribute('data-animal-id');
        if (!animalId) return;
        console.log(`Showing plus dropdown for animal ID: ${animalId}`);

        if (isLoggedIn) {
            // Button: Publish Story Review
            const btnStoryReview = document.createElement('button');
            btnStoryReview.textContent = "發布限時動態心得";
            btnStoryReview.addEventListener('click', (e) => {
                const modal = document.getElementById('reviewSubmitModal');
                if (!modal) return;
                const hiddenAnimalInput = modal.querySelector('input[name="animal_id"]');
                const hiddenTypeInput = modal.querySelector('#submissionType');
                const form = document.getElementById('reviewForm');
                const modalTitle = document.getElementById('reviewSubmitModalTitle');

                if (hiddenAnimalInput) hiddenAnimalInput.value = animalId; else console.error("Hidden input animal_id not found");
                if (hiddenTypeInput) hiddenTypeInput.value = "story"; else console.error("Hidden input submissionType not found");
                if(modalTitle) modalTitle.textContent = "發布限時動態心得";

                if (form) {
                    form.reset(); // Reset form fields
                    // Reset Choices.js selects
                    ['looks', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'sports'].forEach(id => {
                        const selectElement = document.getElementById(id);
                        if (selectElement?.choicesInstance) {
                            try { selectElement.choicesInstance.setChoiceByValue(''); } catch(err){} // Clear selection
                        } else if (selectElement) {
                            selectElement.selectedIndex = 0; // Fallback for non-Choices selects
                        }
                    });
                    // Reset checkboxes and limits
                    ['faceCheckboxes', 'temperamentCheckboxes', 'scaleCheckboxes'].forEach(groupId => {
                        const group = document.getElementById(groupId);
                        if (group) {
                            group.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                                cb.checked = false;
                                cb.disabled = false;
                                const label = cb.closest('label');
                                if (label) label.classList.remove('label-disabled');
                            });
                        }
                    });
                     limitCheckboxSelection('faceCheckboxes', 3);
                     limitCheckboxSelection('temperamentCheckboxes', 3);

                    // Reset and hide price inputs
                    const musicPriceInput = document.getElementById('music_price');
                    if(musicPriceInput) { musicPriceInput.style.display = 'none'; musicPriceInput.value = ''; }
                    const sportsPriceInput = document.getElementById('sports_price');
                    if(sportsPriceInput) { sportsPriceInput.style.display = 'none'; sportsPriceInput.value = ''; }
                    // Re-attach listeners (or ensure they work after reset)
                    togglePriceInput('music', 'music_price');
                    togglePriceInput('sports', 'sports_price');

                 }

                 // Scroll modal body to top
                 const modalBody = modal.querySelector('.modal-body');
                 if(modalBody) modalBody.scrollTop = 0;

                 openModal('reviewSubmitModal');
                 closePlusDropdown(); // Close the menu after opening modal
                 e.stopPropagation(); // Prevent event bubbling
            });
            dropdown.appendChild(btnStoryReview);

            // Button: Write Review
            const btnReview = document.createElement('button');
            btnReview.textContent = "填寫心得";
            btnReview.addEventListener('click', (e) => {
                 const modal = document.getElementById('reviewSubmitModal');
                 if(!modal) return;
                    const hiddenAnimalInput = modal.querySelector('input[name="animal_id"]');
                    const hiddenTypeInput = modal.querySelector('#submissionType');
                    const form = document.getElementById('reviewForm');
                    const modalTitle = document.getElementById('reviewSubmitModalTitle');

                    if (hiddenAnimalInput) hiddenAnimalInput.value = animalId; else console.error("Hidden input animal_id not found");
                    if (hiddenTypeInput) hiddenTypeInput.value = "review"; else console.error("Hidden input submissionType not found");
                    if(modalTitle) modalTitle.textContent = "填寫心得";

                    if(form) {
                        form.reset();
                        // Reset Choices.js selects
                        ['looks', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'sports'].forEach(id => {
                            const selectElement = document.getElementById(id);
                            if (selectElement?.choicesInstance) {
                                try { selectElement.choicesInstance.setChoiceByValue(''); } catch(err){}
                            } else if (selectElement) {
                                selectElement.selectedIndex = 0;
                            }
                        });
                        // Reset checkboxes and limits
                        ['faceCheckboxes', 'temperamentCheckboxes', 'scaleCheckboxes'].forEach(groupId => {
                            const group = document.getElementById(groupId);
                            if (group) {
                                group.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                                    cb.checked = false;
                                    cb.disabled = false; // Re-enable checkboxes
                                    const label = cb.closest('label');
                                    if (label) label.classList.remove('label-disabled');
                                });
                            }
                        });
                         limitCheckboxSelection('faceCheckboxes', 3);
                         limitCheckboxSelection('temperamentCheckboxes', 3);

                        // Reset and hide price inputs
                        const musicPriceInput = document.getElementById('music_price');
                        if(musicPriceInput) { musicPriceInput.style.display = 'none'; musicPriceInput.value = ''; }
                        const sportsPriceInput = document.getElementById('sports_price');
                        if(sportsPriceInput) { sportsPriceInput.style.display = 'none'; sportsPriceInput.value = ''; }
                         togglePriceInput('music', 'music_price');
                         togglePriceInput('sports', 'sports_price');
                     }

                     const modalBody = modal.querySelector('.modal-body');
                     if(modalBody) modalBody.scrollTop = 0;

                     openModal('reviewSubmitModal');
                     closePlusDropdown();
                     e.stopPropagation();
            });
            dropdown.appendChild(btnReview);

            // Button: Add/Remove Pending
            const btnAddWait = document.createElement('button');
            const isPending = row.getAttribute('data-pending') === "true";
            btnAddWait.textContent = isPending ? "移除待約" : "加入待約";
            btnAddWait.addEventListener('click', (e) => {
                togglePending(animalId, !isPending);
                closePlusDropdown();
                e.stopPropagation();
            });
            dropdown.appendChild(btnAddWait);

            // Button: Add/Edit Note
            const btnAddNote = document.createElement('button');
            const noteId = row.getAttribute('data-note-id');
            const noteContent = row.getAttribute('data-note-content') || '';
            btnAddNote.textContent = noteId ? "查看/修改筆記" : "加入筆記";
            btnAddNote.addEventListener('click', (e) => {
                openNoteModal(animalId, noteId, noteContent);
                closePlusDropdown();
                e.stopPropagation();
            });
            dropdown.appendChild(btnAddNote);

        } else {
            // User not logged in
            const infoText = document.createElement('span');
            infoText.textContent = "請先登入以使用功能";
            dropdown.appendChild(infoText);
        }

        // Show the dropdown and overlay
        dropdown.classList.add('open');
        if (bottomOverlay) bottomOverlay.classList.add('open');
    }

    // --- closePlusDropdown function ---
    function closePlusDropdown() {
        const dropdown = document.getElementById('plusDropdown');
        if(dropdown) dropdown.classList.remove('open');
        if(bottomOverlay) bottomOverlay.classList.remove('open');
    }

    // --- processTimeSlotCellsInContainer function ---
     function processTimeSlotCellsInContainer(containerElement) {
         if (!containerElement) return;
         containerElement.querySelectorAll('.time-cell:not(:has(.time-cell-inner))').forEach(td => {
             let text = td.textContent.trim();
             if (!text) return;
             // Improved regex to handle various formats including Chinese characters
             let tokens = text.match(/(\d{1,2}:\d{2}(?:-|~)\d{1,2}:\d{2}|\d{1,2}(?:點|時)?(?:半)?(?:-|~)\d{1,2}(?:點|時)?(?:半)?|\d{1,2}:\d{2}|\d{1,2}(?:點|時)?(?:半)?|[\u4e00-\u9fa5A-Za-z]+(?:-|~)?[\u4e00-\u9fa5A-Za-z]*)/g) || [];
             tokens = tokens.filter(t => t.trim() !== '').map(t => `<span class="time-slot">${escapeHtml(t.trim())}</span>`);
             td.innerHTML = `<div class="time-cell-inner">${tokens.join('')}</div>`;
         });
     }

     // --- Note Row Handling Functions ---
     function applyNoteVisibility(tbody, shouldShow) {
         if (!tbody) return;
         tbody.querySelectorAll('tr.note-row').forEach(noteRow => {
             noteRow.style.display = shouldShow ? '' : 'none';
         });
     }
     function syncCheckboxState(checkbox, tbody) {
         if (!checkbox || !tbody) return;
         const anyNoteRowsExist = tbody.querySelector('tr.note-row');
         checkbox.disabled = !anyNoteRowsExist;
         const label = checkbox.closest('label');
         const labelSpan = checkbox.nextElementSibling; // Assuming span follows checkbox
         if (label) {
             label.style.cursor = checkbox.disabled ? 'not-allowed' : 'pointer';
             if (labelSpan && labelSpan.tagName === 'SPAN') { // Make sure it's the span
                labelSpan.style.opacity = checkbox.disabled ? 0.6 : 1;
             }
         }
     }

    // --- togglePending function ---
    function togglePending(animalId, shouldAdd) {
        if (!isLoggedIn) {
            openModal('loginModal');
            return;
        }
        // *** Use URLS object ***
        const url = shouldAdd ? URLS.add_pending : URLS.remove_pending;
        if (!url) { console.error("Pending URL not found in DJANGO_CONTEXT"); alert("操作失敗：URL配置錯誤"); return; }
        // *** ***
        fetch(url, {
            method: "POST",
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            },
            body: new URLSearchParams({ 'animal_id': animalId })
        })
        .then(response => {
            if (!response.ok) {
                // Try to parse error from JSON response
                return response.json().then(err => {
                    throw new Error(err.error || `伺服器錯誤 ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Update row attribute
                updateRowsByAnimalId(animalId, (r) => {
                    r.setAttribute('data-pending', shouldAdd ? "true" : "false");
                });
                // Update header count
                if (data.pending_count !== undefined) {
                    updatePendingCount(data.pending_count);
                }
                // Refresh pending list modal if open
                const pendingModal = document.getElementById('pendingListModal');
                if (pendingModal && pendingModal.style.display === 'block') {
                     // *** Use the new direct loading function ***
                     loadModalContentDirect(URLS.ajax_get_pending_list, 'pendingListModal');
                }
                // Update button text in dropdown if it's open
                const dropdown = document.getElementById('plusDropdown');
                if (dropdown?.classList.contains('open')) {
                    const pendingButton = Array.from(dropdown.querySelectorAll('button')).find(btn => btn.textContent.includes('待約'));
                    if (pendingButton) {
                        pendingButton.textContent = shouldAdd ? "移除待約" : "加入待約";
                    }
                }
                // Optional: Show success message (e.g., using a toast notification library)
                 if (data.message) { console.log(data.message); } // Or display it to the user
            } else {
                // Handle failure, update count if provided
                 if (data.pending_count !== undefined) { updatePendingCount(data.pending_count); }
                alert(data.error || '操作失敗');
            }
         })
        .catch(error => {
            console.error("Toggle Pending Error:", error);
            alert(`操作待約時發生錯誤: ${error.message}`);
        });
    }

    // --- updatePendingCount function ---
    function updatePendingCount(count) {
        const pendingCountSpan = document.getElementById('pendingCountHeader');
        if (pendingCountSpan) {
            pendingCountSpan.textContent = String(count);
        }
    }

    // --- Note Modal Functions ---
    function openNoteModal(animalId, noteId, noteContent) {
        if (!isLoggedIn) {
            openModal('loginModal');
            return;
        }
        const modal = document.getElementById('noteModal');
        const form = document.getElementById('noteForm');
        const viewSection = document.getElementById('viewNoteSection');
        const title = document.getElementById('noteModalTitle');
        const textarea = document.getElementById('noteContent');
        const viewContentBox = document.getElementById('viewNoteContent');
        const animalIdInput = document.getElementById('noteAnimalId');
        const noteIdInput = document.getElementById('currentNoteId');
        const deleteBtn = document.getElementById('deleteNoteBtn');
        const saveBtn = document.getElementById('saveNoteBtn');
        const viewButtons = document.getElementById('viewNoteButtons');
        const modalBody = modal.querySelector('.modal-body');


        if (!modal || !form || !viewSection || !title || !textarea || !viewContentBox || !animalIdInput || !noteIdInput || !deleteBtn || !saveBtn || !viewButtons || !modalBody) {
            console.error("Note modal elements missing");
            return;
        }

        animalIdInput.value = animalId;
        deleteBtn.setAttribute('data-animal-id', animalId); // Set animalId for delete button too
        form.reset(); // Reset form
        const decodedNoteContent = decodeUnicodeEscapes(noteContent || '');
        textarea.value = decodedNoteContent; // Set content for editing
        modalBody.scrollTop = 0; // Scroll to top

        if (noteId) {
            // Viewing/Editing existing note
            title.textContent = "查看/修改筆記";
            noteIdInput.value = noteId;
            if(viewContentBox) viewContentBox.textContent = decodedNoteContent; // Show content in view box
            viewSection.style.display = 'flex'; // Show view section
            form.style.display = 'none'; // Hide form
            saveBtn.style.display = 'none'; // Hide save button initially
            viewButtons.style.display = 'block'; // Show edit/delete buttons
        } else {
            // Adding new note
            title.textContent = "加入筆記";
            noteIdInput.value = ''; // No existing ID
            if(viewContentBox) viewContentBox.textContent = ''; // Clear view box
            viewSection.style.display = 'none'; // Hide view section
            form.style.display = 'flex'; // Show form
            saveBtn.style.display = 'inline-block'; // Show save button
            viewButtons.style.display = 'none'; // Hide edit/delete buttons
            textarea.focus(); // Focus on textarea
        }
        openModal('noteModal');
    }

    document.getElementById('noteForm')?.addEventListener('submit', function(e) {
        e.preventDefault();
        if (!isLoggedIn) { openModal('loginModal'); return; }

        const modal = document.getElementById('noteModal');
        const formData = new FormData(this);
        const animalId = document.getElementById('noteAnimalId').value;
        const noteId = document.getElementById('currentNoteId').value;
        const newContent = formData.get('content');

        if (!newContent || newContent.trim() === '') {
            alert('筆記內容不能為空');
            return;
        }

        // *** Use URLS object ***
        const url = noteId ? URLS.update_note : URLS.add_note;
        if (!url) { console.error("Note save/update URL not found"); alert("儲存失敗：URL配置錯誤"); return; }
        // *** ***

        fetch(url, {
            method: "POST",
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
                'Accept': 'application/json'
                // 'Content-Type' is not needed for FormData
            },
            body: formData
        })
        .then(res => {
            if (!res.ok) {
                return res.json().then(err => {
                    throw new Error(err.error || `伺服器錯誤 ${res.status}`);
                });
            }
            return res.json();
        })
        .then(data => {
            if (data.success) {
                const currentAnimalId = data.animal_id || animalId;
                const decodedNoteContent = decodeUnicodeEscapes(data.note_content || '');

                // Update note attributes on relevant table rows
                updateRowsByAnimalId(currentAnimalId, (r) => {
                    if (!r.classList.contains('note-row')) { // Exclude the note row itself
                        r.setAttribute('data-note-id', data.note_id);
                        r.setAttribute('data-note-content', decodedNoteContent); // Use decoded content
                    }
                });

                // Refresh relevant open modals
                ['myNotesModal', 'pendingListModal', 'latestReviewModal', 'dailyRecommendationModal', 'dailyScheduleModal', 'findBeauticianModal'].forEach(modalId => {
                      const openModalElement = document.getElementById(modalId);
                      if (openModalElement && openModalElement.style.display === 'block') {
                           console.log(`Note saved/updated, reloading content for open modal: ${modalId}`);
                           if (modalId === 'myNotesModal') {
                               const activeHallLink = openModalElement.querySelector('#myNotesHallMenu a.active');
                               loadFilteredNotes(activeHallLink ? activeHallLink.dataset.hallId : 'all'); // Direct call
                           } else if (modalId === 'dailyScheduleModal') {
                               const activeHallLink = openModalElement.querySelector('#dailyHallMenu a.active');
                               if (activeHallLink) loadFilteredDailySchedule(activeHallLink.dataset.hallId); // Direct call
                           } else if (modalId === 'findBeauticianModal') {
                               performBeauticianSearch(); // Direct call
                           } else if (modalId === 'pendingListModal' && URLS.ajax_get_pending_list) {
                               loadModalContentDirect(URLS.ajax_get_pending_list, modalId);
                           } else if (modalId === 'latestReviewModal' && URLS.ajax_get_latest_reviews) {
                               loadModalContentDirect(URLS.ajax_get_latest_reviews, modalId);
                           } else if (modalId === 'dailyRecommendationModal' && URLS.ajax_get_recommendations) {
                               loadModalContentDirect(URLS.ajax_get_recommendations, modalId);
                           }
                       }
                });


                if(modal) closeModal(modal);
                console.log(data.message || '筆記已儲存');
            } else {
                alert(data.error || '儲存失敗');
            }
        })
        .catch(err => {
            console.error("Save/Update Note Error:", err);
            alert(`儲存筆記時發生錯誤: ${err.message}`);
        });
    });

    document.getElementById('deleteNoteBtn')?.addEventListener('click', function() {
        if (!isLoggedIn) { openModal('loginModal'); return; }

        const modal = document.getElementById('noteModal');
        const noteId = document.getElementById('currentNoteId').value;
        const animalId = this.getAttribute('data-animal-id'); // Get animalId from button

        if (!animalId) return; // Should always have animalId

        if (noteId && confirm("確定要刪除這條筆記嗎？")) {
            const formData = new FormData();
            formData.append('note_id', noteId);

            // *** Use URLS object ***
             const url = URLS.delete_note;
             if (!url) { console.error("Note delete URL not found"); alert("刪除失敗：URL配置錯誤"); return; }
             // *** ***

            fetch(url, {
                method: "POST",
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken,
                    'Accept': 'application/json'
                },
                body: formData
            })
            .then(res => {
                if (!res.ok) {
                    return res.json().then(err => {
                        throw new Error(err.error || `伺服器錯誤 ${res.status}`);
                    });
                }
                return res.json();
            })
            .then(data => {
                if (data.success) {
                    const targetAnimalId = data.animal_id || animalId; // Use returned or button's animalId

                    // Remove note attributes from relevant table rows
                    updateRowsByAnimalId(targetAnimalId, (r) => {
                        if (!r.classList.contains('note-row')) { // Exclude the note row itself
                            r.removeAttribute('data-note-id');
                            r.removeAttribute('data-note-content');
                        }
                    });

                    // Refresh relevant open modals
                     ['myNotesModal', 'pendingListModal', 'latestReviewModal', 'dailyRecommendationModal', 'dailyScheduleModal', 'findBeauticianModal'].forEach(modalId => {
                           const openModalElement = document.getElementById(modalId);
                           if (openModalElement && openModalElement.style.display === 'block') {
                               console.log(`Note deleted, reloading content for open modal: ${modalId}`);
                               if (modalId === 'myNotesModal') {
                                   const activeHallLink = openModalElement.querySelector('#myNotesHallMenu a.active');
                                   loadFilteredNotes(activeHallLink ? activeHallLink.dataset.hallId : 'all'); // Direct call
                               } else if (modalId === 'dailyScheduleModal') {
                                   const activeHallLink = openModalElement.querySelector('#dailyHallMenu a.active');
                                   if (activeHallLink) loadFilteredDailySchedule(activeHallLink.dataset.hallId); // Direct call
                               } else if (modalId === 'findBeauticianModal') {
                                   performBeauticianSearch(); // Direct call
                               } else if (modalId === 'pendingListModal' && URLS.ajax_get_pending_list) {
                                   loadModalContentDirect(URLS.ajax_get_pending_list, modalId);
                               } else if (modalId === 'latestReviewModal' && URLS.ajax_get_latest_reviews) {
                                   loadModalContentDirect(URLS.ajax_get_latest_reviews, modalId);
                               } else if (modalId === 'dailyRecommendationModal' && URLS.ajax_get_recommendations) {
                                   loadModalContentDirect(URLS.ajax_get_recommendations, modalId);
                               }
                           }
                     });

                    if(modal) closeModal(modal);
                    console.log(data.message || '筆記已刪除');
                } else {
                    alert(data.error || '刪除失敗');
                }
            })
            .catch(err => {
                console.error("Delete Note Error:", err);
                alert(`刪除筆記時發生錯誤: ${err.message}`);
            });
        }
    });

    document.getElementById('editNoteBtn')?.addEventListener('click', function() {
        // Switch from view mode to edit mode within the note modal
        const form = document.getElementById('noteForm');
        const viewSection = document.getElementById('viewNoteSection');
        const title = document.getElementById('noteModalTitle');
        const textarea = document.getElementById('noteContent');
        const saveBtn = document.getElementById('saveNoteBtn');
        const viewButtons = document.getElementById('viewNoteButtons');

        if(form && viewSection && title && textarea && saveBtn && viewButtons){
            viewSection.style.display = 'none';
            form.style.display = 'flex';
            title.textContent = "修改筆記"; // Change title
            saveBtn.style.display = 'inline-block';
            viewButtons.style.display = 'none';
            textarea.focus(); // Focus on textarea for editing
        }
    });


    // --- Top Section Update Functions ---
    function updatePhotoArea(areaElement, photoUrl, altText) {
        if (!areaElement) return;
        areaElement.innerHTML = ''; // Clear previous content
        if (photoUrl && photoUrl !== 'None' && photoUrl !== '') {
            const img = document.createElement('img');
            img.src = photoUrl;
            img.alt = altText || '照片';
            img.loading = 'lazy'; // Add lazy loading
            img.style.opacity = 0; // Start hidden for fade-in
            img.onload = () => { img.style.opacity = 1; }; // Fade in on load
            img.onerror = () => { // Handle image loading errors
                areaElement.innerHTML = '<p style="color:#888;font-size:0.9rem;">照片載入失敗</p>';
            };
            areaElement.appendChild(img);
        } else {
            areaElement.innerHTML = '<p style="color:#888;font-size:0.9rem;">無照片</p>';
        }
    }

    function updateIntroArea(introElement, introText) {
        if (!introElement) return;
        const pElement = introElement.querySelector('.intro-top p');
        const introDisplay = introText || '無介紹';
        const decodedIntro = decodeUnicodeEscapes(introDisplay); // Decode content

        if (pElement) {
            pElement.textContent = decodedIntro;
        } else {
            // If structure is missing, recreate it
            introElement.innerHTML = `<div class="intro-top"><p></p></div>`;
            const newPElement = introElement.querySelector('.intro-top p');
            if (newPElement) {
                newPElement.textContent = decodedIntro;
            }
        }
        // Reset scroll position
        const scrollContainer = introElement.querySelector('.intro-top');
        if (scrollContainer) { scrollContainer.scrollTop = 0; } else { introElement.scrollTop = 0; }
    }

    function updateTopSectionFromRow(photoArea, introArea, row) {
        if (!photoArea || !introArea || !row) return;
        const photoUrl = row.dataset.photoUrl || '';
        const introText = row.dataset.introduction || '無介紹';
        const nameElement = row.querySelector('.name');
        const animalName = nameElement ? nameElement.textContent.trim() : '美容師';
        updatePhotoArea(photoArea, photoUrl, animalName);
        updateIntroArea(introArea, introText);
    }

    function updateTopSectionFromData(photoArea, introArea, animalData) {
        if (!photoArea || !introArea || !animalData) return;
        updatePhotoArea(photoArea, animalData.photo_url || '', animalData.name || '美容師');
        updateIntroArea(introArea, animalData.introduction || '無介紹');
    }

    // --- loadReviews function ---
    function loadReviews(animalId) {
        const reviewList = document.getElementById('reviewList');
        if (!reviewList) return;
        reviewList.innerHTML = '<p>載入心得中...</p>'; // Loading indicator

        // *** Use URLS object and add parameter ***
        const baseUrl = URLS.add_review;
        if (!baseUrl) { console.error("Review URL not found"); reviewList.innerHTML = '<p>錯誤：URL配置錯誤</p>'; return; }
        const url = `${baseUrl}?animal_id=${animalId}`;
        // *** ***

        fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest' // Important for Django to recognize AJAX
            }
        })
        .then(response => {
            if (!response.ok) {
                // Try to parse JSON error first
                 return response.json().catch(() => ({ error: `HTTP error ${response.status}` })) // Provide fallback error
                       .then(errData => { throw new Error(errData.error || `HTTP error ${response.status}`); });
            }
            // Check content type BEFORE parsing
            const contentType = response.headers.get("content-type");
            if (!contentType?.includes("application/json")) {
                throw new TypeError(`伺服器未返回有效的 JSON (got ${contentType})`);
            }
            return response.json();
        })
        .then(data => {
            reviewList.innerHTML = ""; // Clear loading/previous content
            if (data?.reviews?.length > 0) {
                data.reviews.forEach(review => {
                    const card = document.createElement('div');
                    card.className = 'review-card';
                    card.dataset.reviewId = review.id; // Store review ID
                    card.dataset.authorId = review.author_id || 'none'; // Store author ID

                    const userTitleSpan = review.user_title ? `<span class="review-user-title">${escapeHtml(review.user_title)}</span>` : '';

                    // Helper to create a review line only if value exists
                    const createReviewLine = (label, value) => {
                        if (value === null || value === undefined || value === '' || (typeof value === 'string' && value.trim() === '')) return '';

                        let displayValue = value;
                        // Handle comma-separated fields
                        if (['臉蛋', '氣質', '尺度'].includes(label) && typeof value === 'string') {
                             displayValue = value.split(',').map(s => s.trim()).filter(s => s).join(', ');
                        }
                        // Handle combined cup fields
                        if (label === '罩杯' && typeof value === 'object') {
                            displayValue = `${value.cup || ''}${value.cup && value.cup_size ? ' - ' : ''}${value.cup_size || ''}`.trim();
                            if (!displayValue) return ''; // Don't show if both are empty
                        }
                         // Handle combined music/sports fields
                         if ((label === '音樂' || label === '體育') && typeof value === 'object') {
                            displayValue = `${value.type || ''}${value.type && value.price ? ` (${value.price})` : ''}`.trim();
                            if (!displayValue) return ''; // Don't show if both are empty
                        }

                        // Decode potential unicode escapes in the final display value
                         const valueSpan = document.createElement('span');
                         valueSpan.className = 'review-value';
                         const decodedDisplayValue = decodeUnicodeEscapes(displayValue); // Decode here
                         valueSpan.textContent = decodedDisplayValue;

                        return `<div class="review-line"><span class="review-label">${escapeHtml(label)}:</span>${valueSpan.outerHTML}</div>`;
                    };

                    // Feedback buttons
                    const feedbackButtonsHTML = `
                        <div class="review-feedback-buttons">
                            <button class="feedback-btn" data-review-id="${review.id}" data-type="good_to_have_you" ${USER_ID === review.author_id ? 'disabled' : ''}>
                                <i class="fas fa-heart"></i> 有你真好
                                <span class="feedback-count" id="count-gthy-${review.id}">${review.good_to_have_you_count || 0}</span>
                            </button>
                            <button class="feedback-btn" data-review-id="${review.id}" data-type="good_looking" ${USER_ID === review.author_id ? 'disabled' : ''}>
                                <i class="fas fa-thumbs-up"></i> 人帥真好
                                <span class="feedback-count" id="count-gl-${review.id}">${review.good_looking_count || 0}</span>
                            </button>
                        </div>
                    `;

                    card.innerHTML = `
                        <div class="review-header">
                            <div class="review-user-info">
                                <span class="review-user">${escapeHtml(review.user || '匿名用戶')}</span>
                                ${userTitleSpan}
                            </div>
                            <span class="review-date">${escapeHtml(review.display_date || '日期未知')}</span>
                        </div>
                        <div class="review-body">
                            ${createReviewLine('年紀', review.age)}
                            ${createReviewLine('顏值', review.looks)}
                            ${createReviewLine('臉蛋', review.face)}
                            ${createReviewLine('氣質', review.temperament)}
                            ${createReviewLine('體態', review.physique)}
                            ${createReviewLine('罩杯', { cup: review.cup, cup_size: review.cup_size })}
                            ${createReviewLine('膚質', review.skin_texture)}
                            ${createReviewLine('膚色', review.skin_color)}
                            ${createReviewLine('音樂', { type: review.music, price: review.music_price })}
                            ${createReviewLine('體育', { type: review.sports, price: review.sports_price })}
                            ${createReviewLine('尺度', review.scale)}
                            ${createReviewLine('心得', review.content)}
                            ${feedbackButtonsHTML}
                        </div>
                    `;
                    reviewList.appendChild(card);
                });
            } else {
                reviewList.innerHTML = '<p>目前沒有相關評論。</p>';
            }
        })
        .catch(error => {
            console.error("Load Reviews Error:", error);
            reviewList.innerHTML = `<p>載入心得時發生錯誤: ${error.message}</p>`;
        });
    }


    // --- Review Form Submit Handler ---
    document.getElementById('reviewForm')?.addEventListener('submit', function(e) {
        e.preventDefault();
        if (!isLoggedIn) {
            openModal('loginModal');
            return;
        }

        const modal = document.getElementById('reviewSubmitModal');
        const animalIdInput = this.querySelector('input[name="animal_id"]');
        const animalId = animalIdInput?.value;
        const submissionTypeInput = this.querySelector('#submissionType');
        const submissionType = submissionTypeInput?.value || 'review'; // Default to 'review'

        if (!animalId) {
            alert('無法獲取美容師 ID，請重試');
            return;
        }

        const formData = new FormData(this);

        // Client-side validation for checkboxes
        if (document.querySelectorAll('#faceCheckboxes input:checked').length > 3) {
            alert('臉蛋最多只能選擇 3 個'); return;
        }
        if (document.querySelectorAll('#temperamentCheckboxes input:checked').length > 3) {
            alert('氣質最多只能選擇 3 個'); return;
        }
        const contentValue = formData.get('content');
        if (!contentValue?.trim()) {
             alert('心得內容不能為空');
             document.getElementById('content').focus();
             return;
        }

        // *** Use URLS object based on submission type ***
        const submitUrl = (submissionType === 'story') ? URLS.add_story_review : URLS.add_review;
        if (!submitUrl) { console.error(`${submissionType} submit URL not found`); alert("提交失敗：URL配置錯誤"); return; }
        // *** ***

        fetch(submitUrl, {
            method: "POST",
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
                'Accept': 'application/json' // Expect JSON response
            }
        })
        .then(res => {
            if (!res.ok) {
                 // Try to parse JSON error first
                 return res.json().then(err => {
                     let errorMsg = err.error || `伺服器錯誤 ${res.status}`;
                     // Append detailed errors if available
                     if (err.errors) {
                          errorMsg += ": " + Object.entries(err.errors).map(([key, value]) => `${key}: ${value}`).join(', ');
                     }
                     throw new Error(errorMsg);
                 }).catch(() => {
                     // If parsing fails, throw generic HTTP error
                      throw new Error(`伺服器錯誤 ${res.status}`);
                 });
            }
            return res.json();
        })
        .then(data => {
            if(data.success) {
                console.log(data.message || '提交成功，待審核');
                if(modal) closeModal(modal); // Close the submission modal

                // Refresh relevant modals *after* successful submission if they are open
                 if (submissionType === 'review') {
                    // Refresh lists that show regular reviews
                     const latestModal = document.getElementById('latestReviewModal');
                     if (latestModal && latestModal.style.display === 'block' && URLS.ajax_get_latest_reviews) {
                        loadModalContentDirect(URLS.ajax_get_latest_reviews, 'latestReviewModal');
                     }
                     const recoModal = document.getElementById('dailyRecommendationModal');
                     if (recoModal && recoModal.style.display === 'block' && URLS.ajax_get_recommendations) {
                        loadModalContentDirect(URLS.ajax_get_recommendations, 'dailyRecommendationModal');
                     }
                     const scheduleModal = document.getElementById('dailyScheduleModal');
                     if (scheduleModal && scheduleModal.style.display === 'block') {
                          const activeHallLink = scheduleModal.querySelector('#dailyHallMenu a.active');
                          if (activeHallLink) { loadFilteredDailySchedule(activeHallLink.dataset.hallId); }
                     }
                      // Refresh Hall of Fame if open
                      const hofModal = document.getElementById('hallOfFameModal');
                      if (hofModal && hofModal.style.display === 'block') { loadHallOfFameData(); }
                 }
                 // (No specific refresh needed for story reviews yet, maybe loadActiveStories?)

            } else {
                alert(data.error || '提交失敗');
            }
        })
        .catch(err => {
            console.error(`Submit ${submissionType} Error:`, err);
            alert(`提交時發生錯誤: ${err.message}`);
        });
    });


    // --- loadFilteredDailySchedule function ---
     function loadFilteredDailySchedule(hallId) {
         const modal = document.getElementById('dailyScheduleModal');
         if (!modal) return;
         const modalBody = modal.querySelector('.modal-body[data-layout="table"]');
         const tbody = modalBody?.querySelector('#dailyAnimalTable tbody');
         const photoArea = modalBody?.querySelector('#dailyPhotoArea');
         const introArea = modalBody?.querySelector('#dailyIntroArea');
         const checkbox = modal.querySelector('.toggle-notes-checkbox[data-table-id="dailyAnimalTable"]');

         if (!tbody || !photoArea || !introArea) {
             console.error("Daily schedule modal elements missing.");
             return;
         }

         // Show loading state
         tbody.innerHTML = '<tr class="loading-message"><td colspan="5">載入中...</td></tr>';
         updatePhotoArea(photoArea, null, '');
         updateIntroArea(introArea, '載入中...');
         if (checkbox) checkbox.disabled = true;

         // *** Use URLS object and add parameter ***
         const baseUrl = URLS.ajax_get_daily_schedule;
         if (!baseUrl) { console.error("Daily schedule URL not found"); tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">錯誤：URL配置錯誤</td></tr>`; return; }
         const url = `${baseUrl}?hall_id=${hallId}`;
         // *** ***

         fetch(url, {
             headers: {
                 'X-Requested-With': 'XMLHttpRequest',
                 'Accept': 'application/json'
             }
         })
         .then(response => {
             if (!response.ok) { throw new Error(`HTTP error ${response.status}`); }
             const ct = response.headers.get('content-type');
             if (!ct?.includes('application/json')) { throw new TypeError('伺服器未返回 JSON'); }
             return response.json();
         })
         .then(data => {
             if (data.table_html !== undefined) {
                 tbody.innerHTML = data.table_html || '<tr class="empty-table-message"><td colspan="5">此館別目前無班表</td></tr>';
                 processTimeSlotCellsInContainer(tbody); // Process new rows

                 // Update top section with first animal's data or clear if none
                 if (data.first_animal && Object.keys(data.first_animal).length > 0) {
                     updateTopSectionFromData(photoArea, introArea, data.first_animal);
                 } else {
                     updatePhotoArea(photoArea, null, '');
                     updateIntroArea(introArea, tbody.querySelector('.empty-table-message') ? '此館別目前無班表' : '此館別目前無介紹');
                 }
                 // Sync and apply note visibility checkbox state
                 if (checkbox) {
                    syncCheckboxState(checkbox, tbody);
                    applyNoteVisibility(tbody, checkbox.checked);
                 }
             } else {
                 // Handle case where backend returned an error in JSON
                 tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">${data.error || '載入班表時發生錯誤'}</td></tr>`;
                 updatePhotoArea(photoArea, null, '');
                 updateIntroArea(introArea, '載入介紹時發生錯誤');
                 if (checkbox) syncCheckboxState(checkbox, tbody);
             }
         })
         .catch(error => {
             console.error("Daily Schedule Fetch Error:", error);
             tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">無法連接伺服器載入班表</td></tr>`;
             updatePhotoArea(photoArea, null, '');
             updateIntroArea(introArea, '無法連接伺服器載入介紹');
             if (checkbox) syncCheckboxState(checkbox, tbody);
         });
     }

    // --- loadFilteredNotes function ---
     function loadFilteredNotes(hallId) {
         const modal = document.getElementById('myNotesModal');
         if (!modal) return; // Button shouldn't show if not logged in anyway

         const modalBody = modal.querySelector('.modal-body[data-layout="table"]');
         const tbody = modalBody?.querySelector('#myNotesTable tbody');
         const photoArea = modalBody?.querySelector('#myNotesPhotoArea');
         const introArea = modalBody?.querySelector('#myNotesIntroArea');
         const checkbox = modal.querySelector('.toggle-notes-checkbox[data-table-id="myNotesTable"]');

         if (!tbody || !photoArea || !introArea) {
             console.error("My Notes modal elements missing.");
             return;
         }

         // Show loading state
         tbody.innerHTML = '<tr class="loading-message"><td colspan="5">載入中...</td></tr>';
         updatePhotoArea(photoArea, null, '');
         updateIntroArea(introArea, '載入中...');
         if (checkbox) checkbox.disabled = true; // Disable checkbox during load

         // *** Use URLS object and add parameter ***
         const baseUrl = URLS.ajax_get_my_notes;
         if (!baseUrl) { console.error("My Notes URL not found"); tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">錯誤：URL配置錯誤</td></tr>`; return; }
         const url = `${baseUrl}?hall_id=${hallId}`;
         // *** ***

         fetch(url, {
             headers: {
                 'X-Requested-With': 'XMLHttpRequest',
                 'Accept': 'application/json'
             }
         })
         .then(response => {
             if (!response.ok) { throw new Error(`HTTP error ${response.status}`); }
             const ct = response.headers.get('content-type');
             if (!ct?.includes('application/json')) { throw new TypeError('伺服器未返回 JSON'); }
             return response.json();
         })
         .then(data => {
             if (data.table_html !== undefined) {
                 tbody.innerHTML = data.table_html || `<tr class="empty-table-message"><td colspan="5">${hallId === 'all' ? '尚無筆記' : '此館別尚無筆記'}</td></tr>`;
                 processTimeSlotCellsInContainer(tbody); // Process new rows

                 // Update top section
                 if (data.first_animal && Object.keys(data.first_animal).length > 0) {
                     updateTopSectionFromData(photoArea, introArea, data.first_animal);
                 } else {
                     updatePhotoArea(photoArea, null, '');
                     updateIntroArea(introArea, tbody.querySelector('.empty-table-message') ? (hallId === 'all' ? '尚無筆記' : '此館別尚無筆記') : '無介紹');
                 }
                 // Sync note checkbox state
                  if (checkbox) {
                    syncCheckboxState(checkbox, tbody);
                    applyNoteVisibility(tbody, checkbox.checked);
                 }
             } else {
                 tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">${data.error || '載入筆記時發生錯誤'}</td></tr>`;
                 updatePhotoArea(photoArea, null, '');
                 updateIntroArea(introArea, '載入介紹時發生錯誤');
                 if (checkbox) syncCheckboxState(checkbox, tbody);
             }
         })
         .catch(error => {
             console.error("My Notes Fetch Error:", error);
             tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">無法連接伺服器載入筆記</td></tr>`;
             updatePhotoArea(photoArea, null, '');
             updateIntroArea(introArea, '無法連接伺服器載入介紹');
              if (checkbox) syncCheckboxState(checkbox, tbody);
         });
     }


    // --- Helper function to load standard table modal content ---
    function loadModalContentDirect(ajaxUrl, modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) { console.warn("Modal not found:", modalId); return; }

        const modalBody = modal.querySelector('.modal-body[data-layout="table"]');
        if (!modalBody) { console.warn("Table layout body not found in modal:", modalId); return; }

        const tableBody = modalBody.querySelector('.body-table tbody');
        const photoArea = modalBody.querySelector('.photo-area');
        const introArea = modalBody.querySelector('.intro-area');
        const checkbox = modal.querySelector('.toggle-notes-checkbox');
        const tableId = checkbox?.dataset.tableId;

        // Check if essential elements exist
        if (!tableBody || !photoArea || !introArea) {
            console.warn("Required elements (tbody, photoArea, introArea) not found in modal:", modalId);
            // Potentially display an error within the modal body here
            modalBody.innerHTML = `<p style="color:red; padding:1rem;">Modal structure error.</p>`;
            return;
        }
        // Check if URL is provided
        if (!ajaxUrl) {
             console.error("loadModalContentDirect: URL is missing for modal:", modalId);
             tableBody.innerHTML = `<tr class="empty-table-message"><td colspan="5">錯誤：URL 未定義</td></tr>`;
             return;
        }

        // Set loading state
        tableBody.innerHTML = '<tr class="loading-message"><td colspan="5">載入中...</td></tr>';
        updatePhotoArea(photoArea, null, '');
        updateIntroArea(introArea, '載入中...');
        if (checkbox) checkbox.disabled = true;

        fetch(ajaxUrl, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) { throw new Error(`HTTP error ${response.status}`); }
            const ct = response.headers.get('content-type');
            if (!ct?.includes('application/json')) { throw new TypeError('伺服器未返回 JSON'); }
            return response.json();
        })
        .then(data => {
            if (data.table_html !== undefined) {
                tableBody.innerHTML = data.table_html || `<tr class="empty-table-message"><td colspan="5">列表是空的</td></tr>`;
                processTimeSlotCellsInContainer(tableBody); // Process time slots

                // Update top section
                if (data.first_animal && Object.keys(data.first_animal).length > 0) {
                    updateTopSectionFromData(photoArea, introArea, data.first_animal);
                } else {
                    updatePhotoArea(photoArea, null, '');
                    // Determine appropriate empty message
                    let emptyMsg = "列表是空的";
                    if (modalId === 'pendingListModal') emptyMsg = '待約清單是空的';
                    else if (modalId === 'latestReviewModal') emptyMsg = '還沒有任何心得';
                    else if (modalId === 'dailyRecommendationModal') emptyMsg = '目前沒有推薦的美容師';
                    updateIntroArea(introArea, emptyMsg);
                }
                // Sync note checkbox state if it exists
                if (checkbox && tableId) {
                    syncCheckboxState(checkbox, tableBody);
                    applyNoteVisibility(tableBody, checkbox.checked);
                }
            } else {
                // Handle case where backend explicitly sent an error in the JSON structure
                 throw new Error(data.error || '資料格式錯誤');
            }
        })
        .catch(error => {
            console.error(`Error loading ${modalId} directly:`, error);
            tableBody.innerHTML = `<tr class="empty-table-message"><td colspan="5">載入失敗: ${error.message}</td></tr>`;
            updatePhotoArea(photoArea, null, '');
            updateIntroArea(introArea, '載入失敗');
             if (checkbox && tableId) syncCheckboxState(checkbox, tableBody); // Still sync checkbox state on error
        });
    }


    // --- Modal Open/Close Functions ---
    const openModal = (modalId) => {
        const modal = document.getElementById(modalId);
        if (!modal) return false; // Modal doesn't exist

        // Scroll specific modal bodies to top on open
        const modalBody = modal.querySelector('.modal-body');
        if(modalBody && ['reviewModal', 'reviewSubmitModal', 'noteModal', 'storyDetailModal', 'hallOfFameModal', 'profileModal', 'chatModal'].includes(modalId)) {
             modalBody.scrollTop = 0;
        }

        // --- Modal Specific Initializations ---
        if (modalId === 'reviewModal') {
            const reviewList = document.getElementById('reviewList');
            if (reviewList) reviewList.innerHTML = '<p>請點擊列表中的心得按鈕查看。</p>'; // Placeholder
        }
        if (modalId === 'storyDetailModal') {
            const headerDiv = document.getElementById('storyDetailHeader');
            const contentDiv = document.getElementById('storyDetailContent');
            if(headerDiv) headerDiv.innerHTML = '<div class="story-loading-message">載入中...</div>';
            if(contentDiv) contentDiv.innerHTML = ''; // Clear previous content
        }
        if (modalId === 'weeklyScheduleModal') {
            const imageArea = document.getElementById('weeklyScheduleImageArea');
            const hallMenu = document.getElementById('weeklyHallMenu');
            if (imageArea) imageArea.innerHTML = '<p>請點擊上方館別查看班表</p>'; // Reset view
            if (hallMenu) hallMenu.querySelectorAll('a').forEach(link => link.classList.remove('active')); // Deactivate tabs
        }
        if (modalId === 'hallOfFameModal') {
            const listElement = document.getElementById('hallOfFameList');
            if(listElement) listElement.innerHTML = '<li class="loading-message">載入中...</li>'; // Reset view
        }
         if (modalId === 'profileModal') {
            const profileBody = document.getElementById('profileModalBody');
            if (profileBody) {
                profileBody.innerHTML = '<div class="profile-loading">載入個人檔案中...</div>'; // Reset view
            }
        }
        if (modalId === 'findBeauticianModal') {
             const searchInput = modal.querySelector('#findBeauticianSearchInput');
             const tbody = modal.querySelector('#findBeauticianTable tbody');
             const photoArea = modal.querySelector('#findBeauticianPhotoArea');
             const introArea = modal.querySelector('#findBeauticianIntroArea');
             // Reset search/filter inputs
             if (searchInput) searchInput.value = '';
             modal.querySelectorAll('.filter-input').forEach(input => {
                if (input.tagName === 'SELECT') input.value = ''; // Reset selects
                else input.value = ''; // Reset number inputs
             });
             // Reset table and top section
             if (tbody) tbody.innerHTML = '<tr class="empty-table-message"><td colspan="5">請輸入姓名或使用篩選器</td></tr>';
             if (photoArea) updatePhotoArea(photoArea, null, '');
             if (introArea) updateIntroArea(introArea, '結果將顯示於下方');
             // Reset notes checkbox
             const checkbox = modal.querySelector('.toggle-notes-checkbox');
             if(checkbox) {
                checkbox.checked = false;
                syncCheckboxState(checkbox, tbody); // Sync state based on potentially empty tbody
             }
              // Focus search input slightly delayed
             setTimeout(() => searchInput?.focus(), 100);
        }
        // Ensure review submit modal title is correct if opened directly
        if (modalId === 'reviewSubmitModal' && !document.getElementById('plusDropdown')?.classList.contains('open')) {
             const modalTitle = document.getElementById('reviewSubmitModalTitle');
             const hiddenTypeInput = document.getElementById('submissionType');
             if(modalTitle) modalTitle.textContent = "填寫心得"; // Default title
             if(hiddenTypeInput) hiddenTypeInput.value = "review"; // Default type
        }
        // Scroll chat to bottom on open
        if (modalId === 'chatModal') {
            const messagesContainer = document.getElementById('chat-messages');
            if (messagesContainer) {
                // Delay slightly to ensure layout is calculated
                 setTimeout(() => { messagesContainer.scrollTop = messagesContainer.scrollHeight; }, 50);
            }
        }


        // Display the modal
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden'; // Prevent background scroll

        // --- Trigger data loading for specific modals ---
        // Using loadModalContentDirect for simple list modals
        if (modalId === 'pendingListModal' && URLS.ajax_get_pending_list) {
             loadModalContentDirect(URLS.ajax_get_pending_list, modalId);
        }
        else if (modalId === 'latestReviewModal' && URLS.ajax_get_latest_reviews) {
             loadModalContentDirect(URLS.ajax_get_latest_reviews, modalId);
        }
        else if (modalId === 'dailyRecommendationModal' && URLS.ajax_get_recommendations) {
             loadModalContentDirect(URLS.ajax_get_recommendations, modalId);
        }
        // Modals with internal logic or filtering trigger their own loads
        else if (modalId === 'dailyScheduleModal') {
             const firstHallLink = modal.querySelector('#dailyHallMenu a:first-of-type');
             const tbody = modal.querySelector('#dailyAnimalTable tbody');
             const photoArea = modal.querySelector('#dailyPhotoArea');
             const introArea = modal.querySelector('#dailyIntroArea');
             const checkbox = modal.querySelector('.toggle-notes-checkbox[data-table-id="dailyAnimalTable"]');
             if (tbody && photoArea && introArea) {
                // Reset to initial state before potentially loading
                 tbody.innerHTML = '<tr class="empty-table-message"><td colspan="5">請點擊下方館別載入班表</td></tr>';
                 updatePhotoArea(photoArea, null, '');
                 updateIntroArea(introArea, '點擊下方館別載入介紹');
                 if (checkbox) syncCheckboxState(checkbox, tbody);
                 modal.querySelectorAll('#dailyHallMenu a').forEach(link => link.classList.remove('active')); // Deactivate all

                 if (firstHallLink) {
                     // Automatically select and load the first hall
                     setTimeout(() => { // Slight delay might help rendering
                        firstHallLink.classList.add('active');
                        loadFilteredDailySchedule(firstHallLink.dataset.hallId);
                     }, 50);
                 } else {
                      // Handle case with no halls
                      tbody.innerHTML = '<tr class="empty-table-message"><td colspan="5">目前沒有任何館別可顯示</td></tr>';
                      updatePhotoArea(photoArea, null, '無館別');
                      updateIntroArea(introArea, '目前沒有任何館別可顯示');
                      if (checkbox) syncCheckboxState(checkbox, tbody);
                 }
             } else {
                 console.error("Daily schedule elements missing on open");
             }
        }
        else if (modalId === 'myNotesModal') {
             // Activate 'All' tab and load all notes
             const hallMenu = modal.querySelector('#myNotesHallMenu');
             if (hallMenu) {
                 hallMenu.querySelectorAll('a').forEach(link => link.classList.remove('active'));
                 const allLink = hallMenu.querySelector('a[data-hall-id="all"]');
                 if (allLink) allLink.classList.add('active');
             }
             loadFilteredNotes('all'); // Load all notes initially
        }
        else if (modalId === 'weeklyScheduleModal') {
             // Automatically trigger click on the first hall link, if exists
             const firstHallLink = modal.querySelector('#weeklyHallMenu a:first-of-type');
             if (firstHallLink) {
                 setTimeout(() => { firstHallLink.click(); }, 50); // Trigger load
             } else {
                  // Handle no halls case
                  const imageArea = document.getElementById('weeklyScheduleImageArea');
                  if (imageArea) imageArea.innerHTML = '<p>目前沒有任何館別可顯示</p>';
             }
        }
        else if (modalId === 'hallOfFameModal') {
            loadHallOfFameData();
        }
         else if (modalId === 'profileModal') {
            if (isLoggedIn) {
                loadProfileData();
            } else {
                 // Show login prompt if trying to access profile when not logged in
                 const profileBody = document.getElementById('profileModalBody');
                 if (profileBody) profileBody.innerHTML = '<div class="profile-error">請先登入以查看個人檔案。</div>';
            }
        }

        return true; // Indicate modal was opened
    };

    const closeModal = (modalElement) => {
        // Ensure we are closing a modal and not the lightbox accidentally
        if (modalElement && modalElement.id !== 'imageLightbox') {
            modalElement.style.display = 'none';
            // Only restore body scroll if NO OTHER modals are open
            const anyModalOpen = document.querySelector('.modal[style*="display: block"]:not(#imageLightbox)');
            if (!anyModalOpen) {
                document.body.style.overflow = ''; // Restore scroll
            }
        }
    };


    // --- showStoryDetail function ---
    function showStoryDetail(storyId) {
        const modal = document.getElementById('storyDetailModal');
        const headerDiv = document.getElementById('storyDetailHeader');
        const contentDiv = document.getElementById('storyDetailContent');
        if (!modal || !headerDiv || !contentDiv) return;

        // Show loading state
        headerDiv.innerHTML = '<div class="story-loading-message">載入動態標頭中...</div>';
        contentDiv.innerHTML = '<div class="story-loading-message">載入動態內容中...</div>';
        openModal('storyDetailModal'); // Open the modal first

        // *** Construct URL using URLS object and parameter ***
         let url = URLS.ajax_get_story_detail; // Get base URL
         if (!url) { console.error("Story detail URL base not found"); headerDiv.innerHTML = `<div class="story-loading-message">錯誤</div>`; contentDiv.innerHTML = `<div class="story-loading-message">URL配置錯誤</div>`; return; }
         // Append ID, ensuring correct slashes
         url = url.endsWith('/') ? `${url}${storyId}/` : `${url}/${storyId}/`;
         // *** ***

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                 return response.json().catch(() => null) // Try to parse error, fallback to null
                       .then(errData => { throw new Error(errData?.error || `HTTP error ${response.status}`); });
            }
            const contentType = response.headers.get("content-type");
            if (!contentType?.includes("application/json")) {
                throw new TypeError("伺服器未返回有效的 JSON");
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.story) {
                const story = data.story;
                const userTitleSpan = story.user_title ? `<span class="review-user-title">${escapeHtml(story.user_title)}</span>` : '';

                // Feedback buttons for story
                const feedbackButtonsHTML = `
                    <div class="review-feedback-buttons">
                        <button class="feedback-btn" data-story-review-id="${story.id}" data-type="good_to_have_you" ${USER_ID === story.author_id ? 'disabled' : ''}>
                            <i class="fas fa-heart"></i> 有你真好
                            <span class="feedback-count" id="count-story-gthy-${story.id}">${story.good_to_have_you_count || 0}</span>
                        </button>
                        <button class="feedback-btn" data-story-review-id="${story.id}" data-type="good_looking" ${USER_ID === story.author_id ? 'disabled' : ''}>
                            <i class="fas fa-thumbs-up"></i> 人帥真好
                            <span class="feedback-count" id="count-story-gl-${story.id}">${story.good_looking_count || 0}</span>
                        </button>
                    </div>
                `;

                // Story Header
                headerDiv.innerHTML = `
                    <div class="story-detail-header-info">
                        ${story.animal_photo_url ? `<img src="${escapeHtml(story.animal_photo_url)}" alt="${escapeHtml(story.animal_name)}">` : '<span class="placeholder" style="font-size: 2.5rem; color:#ccc;">👤</span>'}
                        <div class="text-info">
                            <span class="animal-name">${escapeHtml(story.animal_name || '未知美容師')}</span>
                            <div>
                                ${story.hall_name ? `<span class="hall-name">${escapeHtml(story.hall_name)}</span>` : ''}
                                ${story.remaining_time ? `<span class="remaining-time">${escapeHtml(story.remaining_time)}</span>` : ''}
                            </div>
                        </div>
                    </div>
                `;

                // Story Content (similar to review card)
                const createDetailLine = (label, value) => {
                    if (value === null || value === undefined || value === '' || (typeof value === 'string' && value.trim() === '')) return '';
                    let displayValue = value;
                    if (['臉蛋', '氣質', '尺度'].includes(label) && typeof value === 'string') { displayValue = value.split(',').map(s => s.trim()).filter(s => s).join(', '); }
                    if (label === '罩杯' && typeof value === 'object') { displayValue = `${value.cup || ''}${value.cup && value.cup_size ? ' - ' : ''}${value.cup_size || ''}`.trim(); if (!displayValue) return ''; }
                    if ((label === '音樂' || label === '體育') && typeof value === 'object') { displayValue = `${value.type || ''}${value.type && value.price ? ` (${value.price})` : ''}`.trim(); if (!displayValue) return ''; }
                    const valueSpan = document.createElement('span'); valueSpan.className = 'review-value'; const decodedDisplayValue = decodeUnicodeEscapes(displayValue); valueSpan.textContent = decodedDisplayValue; return `<div class="review-line"><span class="review-label">${escapeHtml(label)}:</span>${valueSpan.outerHTML}</div>`;
                };

                contentDiv.innerHTML = `
                    <div class="review-card" data-story-review-id="${story.id}" data-author-id="${story.author_id || 'none'}">
                        <div class="review-header">
                            <div class="review-user-info">
                                <span class="review-user">${escapeHtml(story.user_name || '匿名用戶')}</span>
                                ${userTitleSpan}
                            </div>
                            <span class="review-date">發布於 ${escapeHtml(story.approved_at_display || '不久前')}</span>
                        </div>
                        <div class="review-body">
                            ${createDetailLine('年紀', story.age)}
                            ${createDetailLine('顏值', story.looks)}
                            ${createDetailLine('臉蛋', story.face)}
                            ${createDetailLine('氣質', story.temperament)}
                            ${createDetailLine('體態', story.physique)}
                            ${createDetailLine('罩杯', { cup: story.cup, cup_size: story.cup_size })}
                            ${createDetailLine('膚質', story.skin_texture)}
                            ${createDetailLine('膚色', story.skin_color)}
                            ${createDetailLine('音樂', { type: story.music, price: story.music_price })}
                            ${createDetailLine('體育', { type: story.sports, price: story.sports_price })}
                            ${createDetailLine('尺度', story.scale)}
                            ${createDetailLine('心得', story.content)}
                            ${feedbackButtonsHTML}
                        </div>
                    </div>
                `;
            } else {
                throw new Error(data.error || '無法獲取動態詳情');
            }
        })
        .catch(error => {
            console.error("Error loading story detail:", error);
            headerDiv.innerHTML = `<div class="story-loading-message">錯誤</div>`;
            contentDiv.innerHTML = `<div class="story-loading-message">無法載入動態內容: ${error.message}</div>`;
        });
    }


    // --- Hall of Fame functions ---
    let hallOfFameDataStore = {}; // Cache fetched data

    function displayRanking(rankType) {
        const listElement = document.getElementById('hallOfFameList');
        const listContainer = document.querySelector('.hof-list-container'); // Get the scrollable container
        if (!listElement || !listContainer) return;

        const rankings = hallOfFameDataStore[rankType];
        listElement.innerHTML = ''; // Clear previous list
        listContainer.scrollTop = 0; // Scroll to top

        if (rankings && rankings.length > 0) {
            rankings.forEach(user => {
                const li = document.createElement('li');
                // Add rank class for styling top 3
                if (user.rank >= 1 && user.rank <= 3) {
                    li.classList.add(`rank-${user.rank}`);
                }

                // Determine icon based on rank
                let iconClass = 'fas fa-trophy'; // Default
                if (user.rank === 1) iconClass = 'fas fa-medal';
                else if (user.rank === 2) iconClass = 'fas fa-award';
                else if (user.rank === 3) iconClass = 'fas fa-star';

                const userTitleSpan = user.user_title ? `<span class="hof-user-title">${escapeHtml(user.user_title)}</span>` : '';
                let countLabel = "次"; // Default
                if (rankType === 'reviews') countLabel = "篇心得";
                else if (rankType === 'stories') countLabel = "篇動態";
                else if (rankType === 'good_looking') countLabel = "次人帥";
                else if (rankType === 'good_to_have_you') countLabel = "次真好";


                li.innerHTML = `
                    <span class="rank"><i class="${iconClass}"></i> #${user.rank}</span>
                    <span class="user-name">${escapeHtml(user.user_name)} ${userTitleSpan}</span>
                    <span class="review-count">${user.count || 0} ${escapeHtml(countLabel)}</span>
                `;
                listElement.appendChild(li);
            });
        } else {
            listElement.innerHTML = '<li class="empty-message">此排行暫無數據</li>';
        }
    }

    function loadHallOfFameData() {
        const listElement = document.getElementById('hallOfFameList');
        const tabsContainer = document.querySelector('#hallOfFameModal .hof-tabs');
        if (!listElement || !tabsContainer) return;

        listElement.innerHTML = '<li class="loading-message">載入中...</li>'; // Show loading
        tabsContainer.querySelectorAll('.hof-tab').forEach(tab => tab.disabled = true); // Disable tabs during load

        // *** Use URLS object ***
         const url = URLS.ajax_get_hall_of_fame;
         if (!url) { console.error("HOF URL not found"); listElement.innerHTML = `<li class="empty-message" style="color: #ff8a8a;">錯誤：URL配置錯誤</li>`; tabsContainer.querySelectorAll('.hof-tab').forEach(tab => tab.disabled = false); return; }
         // *** ***

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                 return response.json().catch(() => ({ error: `HTTP error ${response.status}` }))
                       .then(errData => { throw new Error(errData.error || `HTTP error ${response.status}`); });
            }
            const contentType = response.headers.get("content-type");
            if (!contentType?.includes("application/json")) {
                throw new TypeError("伺服器未返回有效的 JSON");
            }
            return response.json();
        })
        .then(data => {
            tabsContainer.querySelectorAll('.hof-tab').forEach(tab => tab.disabled = false); // Re-enable tabs
            if (data.success && data.rankings) {
                hallOfFameDataStore = data.rankings; // Store fetched data
                const defaultRankType = 'reviews'; // Or whichever tab should be active first
                 // Activate default tab and display its ranking
                 const activeTab = tabsContainer.querySelector(`.hof-tab[data-rank-type="${defaultRankType}"]`);
                 tabsContainer.querySelectorAll('.hof-tab').forEach(tab => {
                     tab.classList.remove('active');
                     tab.setAttribute('aria-selected', 'false');
                 });
                 if (activeTab) {
                     activeTab.classList.add('active');
                     activeTab.setAttribute('aria-selected', 'true');
                 }
                displayRanking(defaultRankType);
            } else {
                throw new Error(data.error || "無法獲取排行數據");
            }
        })
        .catch(error => {
            console.error("Error loading Hall of Fame:", error);
            listElement.innerHTML = `<li class="empty-message" style="color: #ff8a8a;">無法載入名人堂: ${error.message}</li>`;
            tabsContainer.querySelectorAll('.hof-tab').forEach(tab => tab.disabled = false); // Re-enable tabs on error too
        });
    }


    // --- handleFeedbackClick function ---
    function handleFeedbackClick(button) {
        if (!isLoggedIn) { openModal('loginModal'); return; }

        const reviewId = button.dataset.reviewId;
        const storyReviewId = button.dataset.storyReviewId;
        const feedbackType = button.dataset.type;
        const card = button.closest('.review-card'); // Find the parent card
        const authorIdAttr = card?.dataset.authorId; // Get author ID from card

        if ((!reviewId && !storyReviewId) || !feedbackType || !card || !authorIdAttr) {
            alert("無法處理此操作，缺少必要資訊。");
            return;
        }
        // Prevent self-feedback
        if (authorIdAttr !== 'none' && USER_ID === parseInt(authorIdAttr, 10)) {
             alert("不能對自己的心得給予回饋！");
             return;
        }


        button.disabled = true; // Disable button immediately
        button.style.opacity = 0.7; // Visual cue

        const formData = new FormData();
        formData.append('feedback_type', feedbackType);
        if (reviewId) formData.append('review_id', reviewId);
        else if (storyReviewId) formData.append('story_review_id', storyReviewId);

        // *** Use URLS object ***
         const url = URLS.add_review_feedback;
         if (!url) { console.error("Feedback URL not found"); alert("操作失敗：URL配置錯誤"); button.disabled = false; button.style.opacity = 1; return; }
         // *** ***

        fetch(url, {
            method: "POST",
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken,
                'Accept': 'application/json'
            },
            body: formData
        })
        .then(response => {
             if (response.status === 409) { // Conflict - already voted
                 return response.json().then(errData => {
                     alert(errData.error || '你已經給過這個回饋了');
                     // Update counts even if already voted
                     const targetId = reviewId || storyReviewId;
                     const idPrefix = reviewId ? '' : 'story-';
                     const gthyCountSpan = document.getElementById(`count-${idPrefix}gthy-${targetId}`);
                     const glCountSpan = document.getElementById(`count-${idPrefix}gl-${targetId}`);
                     if (gthyCountSpan && errData.good_to_have_you_count !== undefined) gthyCountSpan.textContent = errData.good_to_have_you_count;
                     if (glCountSpan && errData.good_looking_count !== undefined) glCountSpan.textContent = errData.good_looking_count;
                     button.classList.add('clicked'); // Style as clicked
                     throw new Error('Already Voted'); // Special error to prevent further processing
                 });
             }
            if (!response.ok) {
                 return response.json().then(err => { throw new Error(err.error || `伺服器錯誤 ${response.status}`); });
            }
            return response.json();
        })
        .then(data => {
             if (data.success) {
                 // Update counts on success
                 const targetId = reviewId || storyReviewId;
                 const idPrefix = reviewId ? '' : 'story-'; // Prefix for story review count IDs
                 const gthyCountSpan = document.getElementById(`count-${idPrefix}gthy-${targetId}`);
                 const glCountSpan = document.getElementById(`count-${idPrefix}gl-${targetId}`);
                 if (gthyCountSpan && data.good_to_have_you_count !== undefined) gthyCountSpan.textContent = data.good_to_have_you_count;
                 if (glCountSpan && data.good_looking_count !== undefined) glCountSpan.textContent = data.good_looking_count;
                 button.classList.add('clicked'); // Style as successfully clicked
                 console.log(data.message || '回饋成功');
             } else {
                 alert(data.error || '給予回饋失敗');
                 button.disabled = false; // Re-enable on failure
                 button.style.opacity = 1;
             }
        })
        .catch(error => {
            // Don't show error for 'Already Voted'
            if (error.message !== 'Already Voted') {
                 console.error("Feedback Click Error:", error);
                 alert(`處理回饋時發生錯誤: ${error.message}`);
                 button.disabled = false; // Re-enable on other errors
                 button.style.opacity = 1;
            }
        });
    }


    // --- loadProfileData function ---
    function loadProfileData() {
        const profileBody = document.getElementById('profileModalBody');
        if (!profileBody) return;
        profileBody.innerHTML = '<div class="profile-loading">載入個人檔案中...</div>';

        // *** Use URLS object ***
         const url = URLS.ajax_get_profile_data;
         if (!url) { console.error("Profile data URL not found"); profileBody.innerHTML = `<div class="profile-error">錯誤：URL配置錯誤</div>`; return; }
         // *** ***

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                 return response.json().catch(() => null).then(errData => { throw new Error(errData?.error || `HTTP error ${response.status}`); });
            }
            const contentType = response.headers.get("content-type");
            if (!contentType?.includes("application/json")) {
                throw new TypeError("伺服器未返回有效的 JSON");
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.profile_data) {
                const p = data.profile_data;
                const titleBadge = p.user_title ? `<span class="profile-modal-title-badge">${escapeHtml(p.user_title)}</span>` : '';

                // Format used/max counts, handling potential non-numeric values
                const pendingUsed = (typeof p.pending_count === 'number') ? p.pending_count : '?';
                const pendingMax = (typeof p.max_pending_limit === 'number') ? p.max_pending_limit : '?';
                const pendingDisplay = (pendingUsed !== '?' && pendingMax !== '?') ? `${pendingUsed} / ${pendingMax}` : pendingUsed;

                const notesUsed = (typeof p.notes_count === 'number') ? p.notes_count : '?';
                const notesMax = (typeof p.max_notes_limit === 'number') ? p.max_notes_limit : '?';
                const notesDisplay = (notesUsed !== '?' && notesMax !== '?') ? `${notesUsed} / ${notesMax}` : notesUsed;


                profileBody.innerHTML = `
                    <div class="profile-modal-header">
                        <h3>${escapeHtml(p.first_name || p.username)}</h3>
                        ${titleBadge}
                    </div>
                    <div class="profile-modal-stats">
                        <div class="profile-stat-item">
                            <strong>${p.approved_reviews_count !== undefined ? p.approved_reviews_count : '?'}</strong>
                            <span><i class="fas fa-comments"></i> 一般心得</span>
                        </div>
                        <div class="profile-stat-item">
                            <strong>${p.approved_stories_count !== undefined ? p.approved_stories_count : '?'}</strong>
                            <span><i class="fas fa-bolt"></i> 限時心得</span>
                        </div>
                        <div class="profile-stat-item">
                            <strong>${p.good_to_have_you_received !== undefined ? p.good_to_have_you_received : '?'}</strong>
                            <span><i class="fas fa-heart" style="color: #e83e8c;"></i> 收到的「有你真好」</span>
                        </div>
                        <div class="profile-stat-item">
                            <strong>${p.good_looking_received !== undefined ? p.good_looking_received : '?'}</strong>
                            <span><i class="fas fa-thumbs-up" style="color: #17a2b8;"></i> 收到的「人帥真好」</span>
                        </div>
                         <div class="profile-stat-item">
                            <strong>${escapeHtml(pendingDisplay)}</strong>
                            <span><i class="fas fa-calendar-check"></i> 待約清單 (已用/上限)</span>
                        </div>
                         <div class="profile-stat-item">
                            <strong>${escapeHtml(notesDisplay)}</strong>
                            <span><i class="fas fa-sticky-note"></i> 我的筆記 (已用/上限)</span>
                        </div>
                    </div>
                `;
            } else {
                throw new Error(data.error || '無法載入個人檔案資料');
            }
        })
        .catch(error => {
            console.error("Load Profile Data Error:", error);
            profileBody.innerHTML = `<div class="profile-error">無法載入個人檔案: ${error.message}</div>`;
        });
    }


    // --- Debounce function ---
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // --- Function to perform the actual search AJAX call ---
    function performBeauticianSearch() {
        const modal = document.getElementById('findBeauticianModal');
        if (!modal) return;

        const tbody = modal.querySelector('#findBeauticianTable tbody');
        const photoArea = modal.querySelector('#findBeauticianPhotoArea');
        const introArea = modal.querySelector('#findBeauticianIntroArea');
        const checkbox = modal.querySelector('.toggle-notes-checkbox[data-table-id="findBeauticianTable"]');
        const searchInput = modal.querySelector('#findBeauticianSearchInput');
        const minHeightInput = modal.querySelector('#minHeightInput');
        const maxHeightInput = modal.querySelector('#maxHeightInput');
        const minWeightInput = modal.querySelector('#minWeightInput');
        const maxWeightInput = modal.querySelector('#maxWeightInput');
        const cupSelectMin = modal.querySelector('#cupSelectMin');
        const cupSelectMax = modal.querySelector('#cupSelectMax');
        const minFeeInput = modal.querySelector('#minFeeInput');
        const maxFeeInput = modal.querySelector('#maxFeeInput');

        if (!tbody || !photoArea || !introArea || !searchInput || !minHeightInput || !maxHeightInput || !minWeightInput || !maxWeightInput || !cupSelectMin || !cupSelectMax || !minFeeInput || !maxFeeInput) {
            console.error("Search modal elements missing.");
            return;
        }

        const searchTerm = searchInput.value.trim();
        const minHeight = minHeightInput.value.trim();
        const maxHeight = maxHeightInput.value.trim();
        const minWeight = minWeightInput.value.trim();
        const maxWeight = maxWeightInput.value.trim();
        const cupMin = cupSelectMin.value; // Select value is already trimmed
        const cupMax = cupSelectMax.value;
        const minFee = minFeeInput.value.trim();
        const maxFee = maxFeeInput.value.trim();

        const hasKeyword = searchTerm.length > 0;
        const hasFilters = minHeight || maxHeight || minWeight || maxWeight || cupMin || cupMax || minFee || maxFee;

        // If no search term and no filters, show initial message
        if (!hasKeyword && !hasFilters) {
            tbody.innerHTML = '<tr class="empty-table-message"><td colspan="5">請輸入姓名或使用篩選器</td></tr>';
            updatePhotoArea(photoArea, null, '');
            updateIntroArea(introArea, '請輸入姓名或使用篩選器');
            if (checkbox) syncCheckboxState(checkbox, tbody); // Sync checkbox based on empty state
            return;
        }

        // Set loading state
        tbody.innerHTML = '<tr class="loading-message"><td colspan="5">搜尋中...</td></tr>';
        updatePhotoArea(photoArea, null, '');
        updateIntroArea(introArea, '搜尋中...');
        if (checkbox) checkbox.disabled = true;

        // Build query parameters
        const params = new URLSearchParams();
        if (searchTerm) params.append('q', searchTerm);
        if (minHeight) params.append('min_height', minHeight);
        if (maxHeight) params.append('max_height', maxHeight);
        if (minWeight) params.append('min_weight', minWeight);
        if (maxWeight) params.append('max_weight', maxWeight);
        if (cupMin) params.append('cup_min', cupMin);
        if (cupMax) params.append('cup_max', cupMax);
        if (minFee) params.append('min_fee', minFee);
        if (maxFee) params.append('max_fee', maxFee);

        // *** Use URLS object and add parameters ***
         const baseUrl = URLS.ajax_search_beauticians;
         if (!baseUrl) { console.error("Search URL not found"); tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">錯誤：URL配置錯誤</td></tr>`; if(checkbox) checkbox.disabled = false; return; }
         const url = `${baseUrl}?${params.toString()}`;
         // *** ***

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().catch(() => null).then(errData => { throw new Error(errData?.error || `伺服器錯誤 ${response.status}`); });
            }
            const ct = response.headers.get('content-type');
            if (!ct || !ct.includes('application/json')) {
                throw new TypeError('伺服器未返回 JSON');
            }
            return response.json();
        })
        .then(data => {
            if (data.table_html !== undefined) {
                tbody.innerHTML = data.table_html || '<tr class="empty-table-message"><td colspan="5">找不到符合條件的美容師</td></tr>';
                processTimeSlotCellsInContainer(tbody); // Process results

                // Update top section
                if (data.first_animal && Object.keys(data.first_animal).length > 0) {
                    updateTopSectionFromData(photoArea, introArea, data.first_animal);
                } else {
                    updatePhotoArea(photoArea, null, '');
                    updateIntroArea(introArea, tbody.querySelector('.empty-table-message') ? '找不到符合條件的美容師' : '找不到介紹');
                }
                // Sync notes checkbox
                 if (checkbox) {
                    syncCheckboxState(checkbox, tbody);
                    applyNoteVisibility(tbody, checkbox.checked); // Apply visibility based on current state
                 }
            } else {
                throw new Error(data.error || '資料格式錯誤');
            }
         })
        .catch(error => {
            console.error("Beautician Search Error:", error);
            tbody.innerHTML = `<tr class="empty-table-message"><td colspan="5">搜尋失敗: ${error.message}</td></tr>`;
            updatePhotoArea(photoArea, null, '');
            updateIntroArea(introArea, '搜尋失敗');
             if (checkbox) syncCheckboxState(checkbox, tbody); // Sync checkbox on error
        });
    }

    // --- Debounced search handler ---
    const debouncedSearch = debounce(performBeauticianSearch, 300); // 300ms delay

    // --- Global Event Listener Setup (using event delegation) ---
    document.addEventListener('click', function(e) {
        const target = e.target;
        const targetClosest = (selector) => target.closest(selector); // Helper

        // Hall of Fame Tab
        if (targetClosest('.hof-tab')) {
            e.preventDefault();
            const rankType = targetClosest('.hof-tab').dataset.rankType;
            const tabsContainer = targetClosest('.hof-tabs');
            if (rankType && tabsContainer && !targetClosest('.hof-tab').classList.contains('active')) {
                tabsContainer.querySelectorAll('.hof-tab').forEach(tab => {
                     tab.classList.remove('active');
                     tab.setAttribute('aria-selected', 'false');
                });
                targetClosest('.hof-tab').classList.add('active');
                targetClosest('.hof-tab').setAttribute('aria-selected', 'true');
                displayRanking(rankType);
            }
            return; // Handled
        }

        // Profile Button
        if (targetClosest('#btnProfileHeader')) {
            if (isLoggedIn) { openModal('profileModal'); } else { openModal('loginModal'); }
            return;
        }
        // Feedback Button
        if (targetClosest('.feedback-btn')) {
            e.preventDefault();
            handleFeedbackClick(targetClosest('.feedback-btn'));
            return;
        }
        // Story Item
        if (targetClosest('.story-item')) {
            const storyId = targetClosest('.story-item').dataset.storyId;
            if (storyId) { showStoryDetail(storyId); }
            return;
        }
        // Header Buttons to Open Modals
        if (targetClosest('#btnHallOfFameHeader')) { openModal('hallOfFameModal'); return; }
        if (targetClosest('#btnWeeklyScheduleHeader')) { openModal('weeklyScheduleModal'); return; }
        if (targetClosest('#btnDailyScheduleHeader')) { openModal('dailyScheduleModal'); return; }
        if (targetClosest('#latestReviewBtnHeader')) { openModal('latestReviewModal'); return; }
        if (targetClosest('#btnDailyRecommendationHeader')) { openModal('dailyRecommendationModal'); return; }
        if (targetClosest('#pendingListBtnHeader')) { if (isLoggedIn) { openModal('pendingListModal'); } else { openModal('loginModal'); } return; }
        if (targetClosest('#myNotesBtnHeader')) { if (isLoggedIn) { openModal('myNotesModal'); } else { openModal('loginModal'); } return; }
        if (targetClosest('#loginBtnHeader')) { openModal('loginModal'); return; }
        if (targetClosest('#btnFindBeauticianHeader')) { openModal('findBeauticianModal'); return; }
         if (targetClosest('#chat-toggle-button')) { if (isLoggedIn) { openModal('chatModal'); const indicator = document.getElementById('chat-unread-indicator'); if (indicator) indicator.style.display = 'none'; } else { openModal('loginModal'); } return; }


        // Plus Menu Button (inside table rows)
        if (targetClosest('.plus-menu-btn')) {
            e.stopPropagation(); // Prevent row click
            showPlusDropdown(targetClosest('.plus-menu-btn'));
            return;
        }
        // Review Count Button (inside table rows)
        if (targetClosest('.review-count-btn')) {
            e.stopPropagation(); // Prevent row click
            const animalId = targetClosest('.review-count-btn').dataset.animalId;
            if (animalId) {
                loadReviews(animalId);
                openModal('reviewModal');
            }
            return;
        }

        // Hall Menu Links (Daily Schedule)
        if (targetClosest('#dailyHallMenu a')) {
            e.preventDefault();
            const menu = targetClosest('#dailyHallMenu');
            menu.querySelectorAll('a').forEach(item => item.classList.remove('active'));
            targetClosest('#dailyHallMenu a').classList.add('active');
            loadFilteredDailySchedule(targetClosest('#dailyHallMenu a').dataset.hallId);
            return;
        }
        // Hall Menu Links (My Notes)
        if (targetClosest('#myNotesHallMenu a')) {
            e.preventDefault();
            const menu = targetClosest('#myNotesHallMenu');
            menu.querySelectorAll('a').forEach(item => item.classList.remove('active'));
            targetClosest('#myNotesHallMenu a').classList.add('active');
            loadFilteredNotes(targetClosest('#myNotesHallMenu a').dataset.hallId);
            return;
        }
         // Hall Menu Links (Weekly Schedule)
         if (targetClosest('#weeklyHallMenu a')) {
            e.preventDefault();
            const menu = targetClosest('#weeklyHallMenu');
            const hallId = targetClosest('#weeklyHallMenu a').dataset.hallId;
            const imageArea = document.getElementById('weeklyScheduleImageArea');
            if (!hallId || !imageArea) return;

            // Activate tab
            menu.querySelectorAll('a').forEach(item => item.classList.remove('active'));
            targetClosest('#weeklyHallMenu a').classList.add('active');
            imageArea.innerHTML = '<p>載入中...</p>'; // Loading indicator

             // *** Use URLS object and add parameter ***
             const baseUrl = URLS.ajax_get_weekly_schedule;
             if (!baseUrl) { console.error("Weekly schedule URL not found"); imageArea.innerHTML = `<p style="color: red;">錯誤：URL配置錯誤</p>`; return; }
             const url = `${baseUrl}?hall_id=${hallId}`;
             // *** ***

            fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' } })
            .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
            .then(d => {
                imageArea.innerHTML = ''; // Clear loading
                if (d.success && d.schedule_urls?.length > 0) {
                    d.schedule_urls.forEach((imgUrl, i) => {
                        const img = document.createElement('img');
                        img.src = escapeHtml(imgUrl);
                        img.alt = `${escapeHtml(d.hall_name || '館別')} 班表 ${i + 1}`;
                        img.loading = 'lazy'; // Lazy load schedule images
                        imageArea.appendChild(img);
                    });
                } else {
                    imageArea.innerHTML = `<p>${escapeHtml(d.message || d.error || '無法載入班表')}</p>`;
                }
            })
            .catch(err => {
                 imageArea.innerHTML = `<p style="color: red;">無法連接: ${escapeHtml(err.message)}</p>`;
            });
            return;
        }


        // Image Lightbox Trigger (Weekly Schedule or Profile Photo)
        const scheduleImage = targetClosest('#weeklyScheduleImageArea img');
        const profileImage = targetClosest('.photo-area img'); // Target img within photo-area
        if (scheduleImage || profileImage) {
             const imageToShow = scheduleImage || profileImage;
             const lightbox = document.getElementById('imageLightbox');
             const lightboxImg = document.getElementById('lightboxImage');
             if (lightbox && lightboxImg) {
                 lightboxImg.src = imageToShow.src; // Set image source
                 lightboxImg.alt = imageToShow.alt || "放大圖片";
                 lightbox.style.display = 'flex'; // Show lightbox (use flex for centering)
                 document.body.style.overflow = 'hidden'; // Prevent background scroll
             }
             return; // Handled
        }
        // Close Image Lightbox
        const lightbox = document.getElementById('imageLightbox');
        if (lightbox && lightbox.style.display === 'flex') { // Check if lightbox is open
             // Close if clicking the close button OR the background overlay itself
             if (target.id === 'closeLightbox' || target.id === 'imageLightbox') {
                 lightbox.style.display = 'none';
                 const lightboxImg = document.getElementById('lightboxImage');
                 if (lightboxImg) lightboxImg.src = ''; // Clear src
                  // Restore body scroll only if no other modals are open
                 const anyModalOpen = document.querySelector('.modal[style*="display: block"]:not(#imageLightbox)');
                 if (!anyModalOpen) {
                     document.body.style.overflow = '';
                 }
                 return; // Handled
             }
        }
         // Prevent clicks on the lightbox image itself from closing it
         if (target.id === 'lightboxImage') {
            return;
         }


        // Table Row Click (Update Top Section)
        const tableRow = targetClosest('.modal .body-table tbody tr[data-animal-id]:not(.note-row)');
        if (tableRow) {
            // Check if the click was on an interactive element within the row
             if (!targetClosest('.plus-menu-btn, .review-count-btn, a, button, input, select, textarea, .feedback-btn')) {
                const modal = tableRow.closest('.modal');
                // Check if this modal HAS a top section before trying to update
                 if(modal?.querySelector('.modal-body[data-layout="table"] .top-section')){
                     const photoArea = modal.querySelector('.photo-area');
                     const introArea = modal.querySelector('.intro-area');
                     if (photoArea && introArea) {
                         updateTopSectionFromRow(photoArea, introArea, tableRow);
                     }
                 }
            }
            // Don't return here, allow other handlers if needed (though unlikely for row click)
        }

        // Close Modal Button
        const closeBtn = targetClosest('.close-modal');
        if (closeBtn) {
            closeModal(targetClosest('.modal'));
            return; // Handled
        }

        // Click on Modal Backdrop (and not the lightbox backdrop)
        if (target.classList.contains('modal') && target.id !== 'imageLightbox') {
            closeModal(target);
            // Also close plus dropdown if it's open
            if (document.getElementById('plusDropdown')?.classList.contains('open')) {
                closePlusDropdown();
            }
            return; // Handled
        }

        // Click on Bottom Overlay (to close dropdown)
        if (target === bottomOverlay && document.getElementById('plusDropdown')?.classList.contains('open')) {
            closePlusDropdown();
            return; // Handled
        }

    }); // End of global click listener


    // --- Add Listener for Search Input AND New Filters in Find Beautician Modal ---
    const findModal = document.getElementById('findBeauticianModal');
    if (findModal) {
        findModal.querySelectorAll('#findBeauticianSearchInput, .filter-input').forEach(input => {
            // Trigger search on input change (debounced)
            input.addEventListener('input', function() {
                debouncedSearch();
            });
            // Trigger immediate search on Enter key for text/number inputs
            if (input.type === 'number' || input.type === 'search') {
                input.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault(); // Prevent potential form submission
                        performBeauticianSearch(); // Trigger immediately
                    }
                });
            }
             // Trigger immediate search on change for select inputs
             if (input.tagName === 'SELECT') {
                 input.addEventListener('change', function() {
                      performBeauticianSearch(); // Trigger immediately
                 });
             }
        });
    }


    // --- Initializations ---

    // Initialize Choices.js for selects in the review form
    ['looks', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'sports'].forEach(id => {
        const el = document.getElementById(id);
        // Check if element exists and hasn't already been initialized by Choices.js
        if (el && !el.choicesInstance && !el.hasAttribute('data-choice') && !el.classList.contains('choices__input')) {
            try {
                // Determine if the first option is a placeholder
                const ph = el.options[0]?.value === "";
                el.choicesInstance = new Choices(el, {
                    searchEnabled: false, // Disable search within dropdown
                    itemSelectText: '', // Text shown on hover/focus selection
                    allowHTML: false, // Prevent HTML injection
                    shouldSort: false, // Keep original option order
                    placeholder: ph, // Enable placeholder if first option is empty
                    placeholderValue: ph ? el.options[0].text : null // Use first option's text as placeholder
                });
            } catch (e) {
                 console.error(`Choices init error for #${id}:`, e);
            }
        }
    });

    // Toggle price input visibility based on select value
    function togglePriceInput(selectId, priceInputId) {
        const sel = document.getElementById(selectId);
        const inp = document.getElementById(priceInputId);
        if (!sel || !inp) return;

        const updateVisibility = () => {
             inp.style.display = (sel.value === '可加值') ? 'block' : 'none';
             if (sel.value !== '可加值') inp.value = ''; // Clear price if not applicable
        };

        // Ensure listener isn't added multiple times if function is called again
        sel.removeEventListener('change', updateVisibility);
        sel.addEventListener('change', updateVisibility);
        // Call once initially in case the form is pre-filled or re-opened
        // Use a slight delay to ensure Choices.js might have initialized
        setTimeout(updateVisibility, 150);
    }
    togglePriceInput('music', 'music_price');
    togglePriceInput('sports', 'sports_price');

    // Fade out login error message
    const loginErrorMsg = document.getElementById('login-error-message');
    if (loginErrorMsg) {
        setTimeout(() => {
            loginErrorMsg.style.transition = 'opacity 0.5s ease';
            loginErrorMsg.style.opacity = '0';
            setTimeout(() => { loginErrorMsg.style.display = 'none'; }, 500); // Remove after fade
        }, 4000); // Start fading after 4 seconds
    }

    // Limit checkbox selections
    function limitCheckboxSelection(groupId, maxCount) {
        const group = document.getElementById(groupId);
        if (!group) return;
        const cbs = group.querySelectorAll('input[type="checkbox"]');

        const checkLimit = () => {
            const checkedCount = group.querySelectorAll('input:checked').length;
            cbs.forEach(cb => {
                const l = cb.closest('label');
                // Disable unchecked boxes if limit is reached
                 cb.disabled = !cb.checked && checkedCount >= maxCount;
                 // Add/remove disabled class to label for styling
                 if(l) l.classList.toggle('label-disabled', cb.disabled);
            });
        };
        // Attach listener to each checkbox in the group
        cbs.forEach(cb => {
             // Ensure listener isn't added multiple times
             cb.removeEventListener('change', checkLimit);
             cb.addEventListener('change', checkLimit);
        });
        // Initial check in case form is pre-filled
        checkLimit();
    }
    limitCheckboxSelection('faceCheckboxes', 3);
    limitCheckboxSelection('temperamentCheckboxes', 3);

     // Add change listeners to all "Toggle Notes" checkboxes
     function handleNoteCheckboxChange() {
         if (this.disabled) return; // Don't do anything if disabled
         const tableId = this.dataset.tableId;
         const modal = this.closest('.modal');
         if (!modal) return;
         const tbody = modal.querySelector(`#${tableId} tbody`);
         if (!tbody) return;
         applyNoteVisibility(tbody, this.checked);
     }
     document.querySelectorAll('.toggle-notes-checkbox').forEach(cb => {
         // Ensure listener isn't added multiple times
         cb.removeEventListener('change', handleNoteCheckboxChange);
         cb.addEventListener('change', handleNoteCheckboxChange);
     });
     // Initial sync after slight delay to allow dynamic content loading
     setTimeout(() => {
         document.querySelectorAll('.toggle-notes-checkbox').forEach(cb => {
              const tid = cb.dataset.tableId;
              const m = cb.closest('.modal');
              if (tid && m) {
                  const tb = m.querySelector(`#${tid} tbody`);
                  if (tb) syncCheckboxState(cb, tb);
              }
         });
     }, 150);


    // --- loadActiveStories function ---
    function loadActiveStories() {
        const storyPanel = document.getElementById('storyReviewPanel');
        if (!storyPanel) return;

        // Only show loading message if panel is empty or previous load failed
        const existingMessage = storyPanel.querySelector('.story-loading-message');
        if (!storyPanel.innerHTML.trim() || (existingMessage && existingMessage.style.color === 'red')) {
             storyPanel.innerHTML = '<div class="story-loading-message">載入限時動態中...</div>';
        }

        // *** Use URLS object ***
         const url = URLS.ajax_get_active_stories;
         if (!url) { console.error("Active stories URL not found"); storyPanel.innerHTML = `<div class="story-loading-message" style="color: red;">錯誤：URL配置錯誤</div>`; return; }
         // *** ***

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json'
            }
        })
        .then(r => {
            if (!r.ok) {
                 return r.json().catch(() => null).then(errData => {
                      console.error(`[Stories Fetch Error] Status: ${r.status}, Body:`, errData);
                      throw new Error(errData?.error || `HTTP error ${r.status}`);
                 });
            }
             const contentType = r.headers.get("content-type");
             if (!contentType || !contentType.includes("application/json")) {
                 throw new TypeError("伺服器未返回有效的 JSON");
             }
            return r.json();
        })
        .then(data => {
            storyPanel.innerHTML = ''; // Clear previous stories/loading message
            if (data.stories?.length > 0) {
                data.stories.forEach(story => {
                    const itemDiv = document.createElement('div');
                    itemDiv.className = 'story-item';
                    itemDiv.dataset.storyId = story.id;
                    itemDiv.dataset.animalId = story.animal_id; // Store animal ID if needed

                    const photoDiv = document.createElement('div');
                    photoDiv.className = 'story-item-photo';
                    if (story.animal_photo_url) {
                        const img = document.createElement('img');
                        img.src = escapeHtml(story.animal_photo_url);
                        img.alt = escapeHtml(story.animal_name);
                        img.loading = 'lazy'; // Lazy load story photos
                        img.onerror = function() { this.parentNode.innerHTML = '<span class="placeholder">👤</span>'; }; // Fallback
                        photoDiv.appendChild(img);
                    } else {
                        const p = document.createElement('span');
                        p.className = 'placeholder'; p.textContent = '👤';
                        photoDiv.appendChild(p);
                    }

                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'story-item-name';
                    nameSpan.textContent = escapeHtml(story.animal_name);

                    const hallSpan = document.createElement('span');
                    hallSpan.className = 'story-item-hall';
                    hallSpan.textContent = escapeHtml(story.hall_name);

                    const timeSpan = document.createElement('span');
                    timeSpan.className = 'story-item-time';
                    timeSpan.textContent = escapeHtml(story.remaining_time);

                    itemDiv.appendChild(photoDiv);
                    itemDiv.appendChild(nameSpan);
                    itemDiv.appendChild(hallSpan);
                    itemDiv.appendChild(timeSpan);
                    storyPanel.appendChild(itemDiv);
                });
            } else {
                storyPanel.innerHTML = '<div class="story-loading-message">目前沒有限時動態</div>';
            }
        })
        .catch(error => {
            console.error("[loadActiveStories] Fetch/Processing Error:", error);
            storyPanel.innerHTML = `<div class="story-loading-message" style="color: red;">無法載入動態: ${escapeHtml(error.message)}</div>`;
        });
    }

    // Prevent dragging on non-selectable areas
    const dragPreventHandler = (event) => {
        const target = event.target;
        let allowDrag = false;
        let current = target;

        // Check if the target or any parent allows text selection
        while (current && current !== document.body) {
             // Explicitly allow drag/selection on form elements
            if (current.matches('input, textarea, select, [contenteditable="true"]')) {
                 allowDrag = true;
                 break;
            }
            // Check computed style for user-select
            const userSelectStyle = window.getComputedStyle(current).webkitUserSelect || window.getComputedStyle(current).userSelect;
            if (userSelectStyle === 'text' || userSelectStyle === 'auto' || userSelectStyle === 'element') {
                 // Allow if it's within a known selectable container, otherwise default to prevent
                 if (target.closest('.modal-body[data-layout="table"] .body-table td, .portal-content p, .introduction, .review-value, #viewNoteContent, #chat-messages .chat-message span:not(.chat-message-header):not(.chat-message-time):not(.chat-user-title), .note-box, #profileModal .modal-body, .quoted-message-preview')) {
                    allowDrag = true;
                 } else {
                     allowDrag = false; // Prevent dragging on general 'auto'/'text' areas unless specified
                 }
                 break; // Stop checking parent styles once a rule is found
            } else if (userSelectStyle === 'none') {
                 allowDrag = false; // Explicitly disallowed
                 break;
            }
            current = current.parentElement;
        }

        if (!allowDrag) {
            event.preventDefault();
        }
    };

    // Apply drag prevention to main content and modal contents
    const mainContent = document.querySelector('.content');
    if (mainContent) {
        mainContent.addEventListener('dragstart', dragPreventHandler);
        mainContent.setAttribute('draggable', 'false'); // Discourage dragging appearance
    }
    const modalContents = document.querySelectorAll('.modal-content');
    modalContents.forEach(mc => {
        mc.addEventListener('dragstart', dragPreventHandler);
        mc.setAttribute('draggable', 'false');
    });

    // --- Initial function calls ---
    loadActiveStories(); // Load stories on page load
    setInterval(loadActiveStories, 60000); // Refresh stories every minute


    console.log("MyApp main script loaded (V20 - Refactored Views/URLs).");

}); // End of DOMContentLoaded listener