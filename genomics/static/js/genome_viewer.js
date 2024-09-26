function initGenomeViewer(
    sequence,
    startPos,
    endPos,
    sequenceLength,
    features,
    highlightedFeatureStart,
    highlightedFeatureEnd,
    nucleotideData,
    colorBy,
    interactions
) {
    // Show the loading overlay
    document.getElementById('loading-overlay').classList.remove('hidden');

    const sequenceViewer = document.getElementById('sequence-viewer');

    // Listener for color scheme changes
    const colorSchemeSelect = document.getElementById('colorSchemeSelect');
    colorSchemeSelect.addEventListener('change', function () {
        const selectedColorBy = colorSchemeSelect.value;

        // Update the URL parameters and reload the page
        const params = new URLSearchParams(window.location.search);
        params.set('color_by', selectedColorBy);

        window.location.href = `${window.location.pathname}?${params.toString()}`;
    });

    // Map positions to features for quick lookup
    const positionFeatureMap = {};

    features.forEach((feature) => {
        for (let pos = feature.start; pos <= feature.end; pos++) {
            if (!positionFeatureMap[pos]) {
                positionFeatureMap[pos] = [];
            }
            positionFeatureMap[pos].push(feature);
        }
    });

    // Visualize sequence with highlighted features and coloring
    function displaySequence(seq, start) {
        sequenceViewer.innerHTML = '';

        const seqLength = seq.length;
        const charsPerLine = Math.floor(sequenceViewer.clientWidth / 12); // Adjust based on nt-box width
        const lines = Math.ceil(seqLength / charsPerLine);

        for (let line = 0; line < lines; line++) {
            const lineStartIndex = line * charsPerLine;
            const lineEndIndex = Math.min((line + 1) * charsPerLine, seqLength);

            const nucleotideContainer = document.createElement('div');
            nucleotideContainer.classList.add('nucleotide-container');

            for (let i = lineStartIndex; i < lineEndIndex; i++) {
                const nt = seq[i];
                const pos = start + i + 1;
                const ntDiv = document.createElement('div');
                ntDiv.classList.add('nt-box');
                ntDiv.textContent = nt;
                ntDiv.dataset.nt = nt.toUpperCase();
                ntDiv.title = `Position ${pos}`;
                ntDiv.id = `nt-box-${pos}`;

                if (positionFeatureMap[pos]) {
                    ntDiv.classList.add('feature-nt');
                    // Add feature info to tooltip
                    const featureInfo = positionFeatureMap[pos].map(f => `${f.type}: ${f.description}`).join('\n');
                    ntDiv.title += `\nFeatures:\n${featureInfo}`;
                }

                if (highlightedFeatureStart && highlightedFeatureEnd &&
                    pos >= highlightedFeatureStart && pos <= highlightedFeatureEnd) {
                    ntDiv.classList.add('selected-feature');
                }

                // Apply coloring
                if (colorBy === 'nucleotide') {
                    // Do nothing, coloring is applied via CSS
                } else if (nucleotideData && nucleotideData[i] != null) {
                    const value = nucleotideData[i];
                    ntDiv.style.backgroundColor = valueToColor(value);
                } else {
                    ntDiv.style.backgroundColor = '#CCCCCC'; // Default color if data missing
                }

                nucleotideContainer.appendChild(ntDiv);
            }

            sequenceViewer.appendChild(nucleotideContainer);
        }

        drawInteractions();
    }

    // Function to map values between -1 and 1 to colors
    function valueToColor(value) {
        // Adjust value to be between -1 and 1
        value = Math.max(-1, Math.min(1, value));

        let h = ((1 - value) * 120).toString(10);
        return ["hsl(", h, ",100%,50%)"].join("");
    }

    function drawInteractions() {
        // Remove any existing SVG overlay
        const existingSvg = document.getElementById('interactions-overlay');
        if (existingSvg) {
            existingSvg.remove();
        }

        // Create SVG overlay
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.id = 'interactions-overlay';
        svg.style.position = 'absolute';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.width = `${sequenceViewer.scrollWidth}px`;
        svg.style.height = `${sequenceViewer.scrollHeight}px`;
        svg.style.pointerEvents = 'none';
        svg.style.zIndex = '10';

        sequenceViewer.style.position = 'relative';
        sequenceViewer.appendChild(svg);

        interactions.forEach(function(interaction) {
            const fromPos = interaction.from_position;
            const toPos = interaction.to_position;
            const weight = interaction.weight;

            const fromElement = document.getElementById(`nt-box-${fromPos}`);
            const toElement = document.getElementById(`nt-box-${toPos}`);

            if (fromElement && toElement) {
                const fromRect = fromElement.getBoundingClientRect();
                const toRect = toElement.getBoundingClientRect();

                const sequenceViewerRect = sequenceViewer.getBoundingClientRect();

                const x1 = fromRect.left - sequenceViewerRect.left + fromRect.width / 2;
                const y1 = fromRect.top - sequenceViewerRect.top + fromRect.height / 2;

                const x2 = toRect.left - sequenceViewerRect.left + toRect.width / 2;
                const y2 = toRect.top - sequenceViewerRect.top + toRect.height / 2;

                // Calculate control points for a curved path
                const deltaX = x2 - x1;
                const deltaY = y2 - y1;
                const controlPointX = x1 + deltaX / 2;
                const controlPointY = y1 - Math.min(100, Math.abs(deltaX) / 2); // Control the curvature

                // Use cubic Bezier curve for smoother line
                const pathData = `M${x1},${y1} C${x1},${controlPointY} ${x2},${controlPointY} ${x2},${y2}`;

                // Create a path element for the curve
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                path.setAttribute('d', pathData);

                const strokeColor = `rgba(255, 0, 0, ${weight})`;
                path.setAttribute('stroke', strokeColor);
                path.setAttribute('stroke-width', '2');
                path.setAttribute('fill', 'none');

                // Add title for tooltip
                const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                title.textContent = `From: ${fromPos}\nTo: ${toPos}\nWeight: ${interaction.weight}`;
                path.appendChild(title);

                svg.appendChild(path);
            } else {
                console.warn(`Interaction positions not found in the current view: from ${fromPos} to ${toPos}`);
            }
        });
    }

    // Initial display
    displaySequence(sequence, startPos);

    // Initialize DataTables for the all-features table
    $(document).ready(function () {
        $('#all-features-table').DataTable({
            paging: true,
            searching: true,
            ordering: true,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]],
            rowCallback: function(row, data) {
                $(row).on('click', function() {
                    const featureId = $(this).data('feature-id');
                    const featureStart = $(this).data('feature-start');
                    const featureEnd = $(this).data('feature-end');
                    navigateToFeature(featureStart, featureEnd);
                    highlightFeature(featureId);
                });
            }
        });

        // Initialize DataTables for the displayed-features table
        $('#displayed-features-table').DataTable({
            paging: false,
            searching: false,
            ordering: true,
            info: false,
            columns: [
                { data: 'start' },
                { data: 'end' },
                { data: 'description' }
            ]
        });

        // Add click event handler to rows
        $('#displayed-features-table tbody').on('click', 'tr', function () {
            const featureId = $(this).data('feature-id');
            highlightFeature(featureId);
        });

        // Hide the loading overlay after everything is ready
        document.getElementById('loading-overlay').classList.add('hidden');
    });

    // Function to highlight a feature
    function highlightFeature(featureId) {
        // Remove previous highlights
        document.querySelectorAll('.highlighted-feature').forEach(function(elem) {
            elem.classList.remove('highlighted-feature');
        });

        // Find the feature
        const feature = features.find(f => f.id === featureId);
        if (feature) {
            // Highlight the nucleotides in the feature
            for (let pos = feature.start; pos <= feature.end; pos++) {
                const ntDiv = document.getElementById(`nt-box-${pos}`);
                if (ntDiv) {
                    ntDiv.classList.add('highlighted-feature');
                }
            }
        }
    }

    // Add event listeners to navigation buttons
    document.getElementById('back-button').addEventListener('click', function () {
        navigateBackward();
    });

    document.getElementById('forward-button').addEventListener('click', function () {
        navigateForward();
    });

    function navigateBackward() {
        let newStart = startPos - (endPos - startPos);
        let newEnd = startPos;

        if (newStart < 0) {
            newStart = 0;
            newEnd = endPos - startPos;
        }

        updateUrlAndReload(newStart, newEnd);
    }

    function navigateForward() {
        let newStart = endPos;
        let newEnd = endPos + (endPos - startPos);

        if (newEnd > sequenceLength) {
            newEnd = sequenceLength;
            newStart = sequenceLength - (endPos - startPos);
            if (newStart < 0) newStart = 0;
        }

        updateUrlAndReload(newStart, newEnd);
    }

    function updateUrlAndReload(newStart, newEnd, highlightStart, highlightEnd) {
        const params = new URLSearchParams(window.location.search);
        params.set('start', newStart);
        params.set('end', newEnd);
        if (highlightStart && highlightEnd) {
            params.set('highlighted_start', highlightStart);
            params.set('highlighted_end', highlightEnd);
        }

        // Include selected color scheme in the URL parameters
        params.set('color_by', colorSchemeSelect.value);

        window.location.href = window.location.pathname + '?' + params.toString();
    }

    // Function to handle feature navigation
    function navigateToFeature(featureStart, featureEnd) {
        let newStart = Math.max(0, featureStart - 2500);
        let newEnd = Math.min(sequenceLength, featureEnd + 2500);

        updateUrlAndReload(newStart, newEnd, featureStart, featureEnd);
    }

    // Handle window resize to adjust line wrapping and redraw the interactions
    window.addEventListener('resize', function () {
        displaySequence(sequence, startPos);
    });
}