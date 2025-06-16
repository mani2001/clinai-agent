// Semantic Search JavaScript
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const resultsContainer = document.getElementById('resultsContainer');
const searchResults = document.getElementById('searchResults');
const loadingSpinner = document.getElementById('loadingSpinner');

// Search functionality
async function performSearch(query) {
    if (!query.trim()) {
        alert('Please enter a search query');
        return;
    }

    // Show loading
    loadingSpinner.style.display = 'block';
    resultsContainer.style.display = 'none';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query.trim() })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        displayResults(data.results || [], query);

    } catch (error) {
        console.error('Search error:', error);
        displayError('Failed to perform search. Please try again.');
    } finally {
        loadingSpinner.style.display = 'none';
    }
}

// Display search results
function displayResults(results, query) {
    resultsContainer.style.display = 'block';
    
    if (results.length === 0) {
        searchResults.innerHTML = `
            <div class="no-results">
                <i class="bi bi-search fs-1 text-muted mb-3"></i>
                <h5>No results found</h5>
                <p>No patients found matching "${query}". Try adjusting your search terms or using different keywords.</p>
            </div>
        `;
        return;
    }

    const resultsHtml = results.map((patient, index) => {
        // Parse keywords if they're a string
        let keywords = [];
        if (patient.keywords) {
            if (typeof patient.keywords === 'string') {
                keywords = patient.keywords.split(',').map(k => k.trim()).filter(k => k && k !== 'No main keywords found.');
            } else if (Array.isArray(patient.keywords)) {
                keywords = patient.keywords;
            }
        }

        const keywordTags = keywords.slice(0, 5).map(keyword => 
            `<span class="keyword-tag">${keyword}</span>`
        ).join('');

        return `
            <a href="/patient/${patient.patient_id}" class="patient-result-card">
                <div class="patient-card-header d-flex justify-content-between align-items-center">
                    <span class="patient-id">ID: ${patient.patient_id}</span>
                    <span class="relevance-score">${patient.relevance_score}% match</span>
                </div>
                <div class="patient-info">
                    <div><strong>Name:</strong> ${patient.name || 'N/A'}</div>
                    <div><strong>Age:</strong> ${patient.age || 'N/A'}</div>
                    <div><strong>Gender:</strong> ${patient.gender || 'N/A'}</div>
                </div>
                <div class="patient-summary">
                    <strong>Summary:</strong> ${truncateText(patient.summary || 'No summary available', 200)}
                </div>
                ${keywords.length > 0 ? `
                    <div class="patient-keywords">
                        <strong class="me-2">Keywords:</strong>
                        ${keywordTags}
                        ${keywords.length > 5 ? '<span class="keyword-tag">+' + (keywords.length - 5) + ' more</span>' : ''}
                    </div>
                ` : ''}
            </a>
        `;
    }).join('');

    searchResults.innerHTML = resultsHtml;
}

// Display error message
function displayError(message) {
    resultsContainer.style.display = 'block';
    searchResults.innerHTML = `
        <div class="no-results">
            <i class="bi bi-exclamation-triangle fs-1 text-warning mb-3"></i>
            <h5>Search Error</h5>
            <p>${message}</p>
        </div>
    `;
}

// Truncate text helper
function truncateText(text, maxLength) {
    if (text.length <= maxLength) return text;
    return text.substr(0, maxLength) + '...';
}

// Example search function
function searchExample(query) {
    searchInput.value = query;
    performSearch(query);
}

// Event listeners
searchBtn.addEventListener('click', () => {
    performSearch(searchInput.value);
});

searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        performSearch(searchInput.value);
    }
});

// Focus search input on page load
searchInput.focus();