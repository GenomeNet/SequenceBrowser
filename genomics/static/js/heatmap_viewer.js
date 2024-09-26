document.addEventListener('DOMContentLoaded', () => {
    const featureTable = document.getElementById('displayed-features-table');
    let selectedRow = null;

    if (featureTable) {
        featureTable.addEventListener('click', (event) => {
            const row = event.target.closest('tr');
            if (row) {
                const featureId = row.getAttribute('data-feature-id');
                if (featureId) {
                    if (selectedRow) {
                        selectedRow.classList.remove('selected-row');
                    }
                    row.classList.add('selected-row');
                    selectedRow = row;
                    updateFeaturePlot(featureId);
                }
            }
        });
    }
});

function updateFeaturePlot(featureId) {
    const contig = document.querySelector('meta[name="contig"]').getAttribute('content');
    fetch(`/viewer/${contig}/feature-data?feature_id=${featureId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error(data.error);
                return;
            }
            plotFeatureData(data.feature_data, data.feature);
        })
        .catch(error => console.error('Error fetching feature data:', error));
}

function plotFeatureData(data, featureInfo) {
    // Clear any existing plots
    d3.select("#feature-plot-container").html("");

    // Check if data is empty
    if (data.length === 0) {
        d3.select("#feature-plot-container")
            .append("p")
            .text("No data available for this feature.");
        return;
    }

    const container = d3.select("#feature-plot-container");
    const containerWidth = container.node().getBoundingClientRect().width;
    const margin = { top: 20, right: 20, bottom: 20, left: 50 };
    const width = containerWidth - margin.left - margin.right;
    const trackHeight = 20; // Height of each data track
    const height = data.length * trackHeight + margin.top + margin.bottom;

    const svg = container.append("svg")
        .attr("width", containerWidth)
        .attr("height", height);

    const g = svg.append("g")
        .attr("transform", `translate(${margin.left},${margin.top})`);

    // Get the list of positions within the feature
    const positions = data[0].values.map(d => d.position);

    // Create a scale for the x-axis (positions)
    const xScale = d3.scaleBand()
        .domain(positions)
        .range([0, width])
        .padding(0);

    // Create a color scale based on the overall min and max values
    const allValues = data.flatMap(d => d.values.map(v => v.value));
    const minValue = d3.min(allValues);
    const maxValue = d3.max(allValues);
    const colorScale = d3.scaleSequential(d3.interpolateViridis)
        .domain([maxValue, minValue]); // Inverted to have higher values lighter

    // For each data track, create a row of colored rectangles
    data.forEach((track, trackIndex) => {
        const group = g.append("g")
            .attr("transform", `translate(0, ${trackIndex * trackHeight})`);

        // Add track label
        group.append("text")
            .attr("x", -10)
            .attr("y", trackHeight / 2)
            .attr("dy", "0.35em")
            .attr("text-anchor", "end")
            .style("font-size", "12px")
            .text(track.name);

        // Add colored rectangles for each position
        group.selectAll("rect")
            .data(track.values)
            .enter()
            .append("rect")
            .attr("x", d => xScale(d.position))
            .attr("y", 0)
            .attr("width", xScale.bandwidth())
            .attr("height", trackHeight)
            .style("fill", d => colorScale(d.value));
    });

    // Optional: Add x-axis if needed
    /*
    const xAxis = d3.axisBottom(xScale)
        .tickValues(positions.filter((d, i) => i % 10 === 0)) // Show every 10th position
        .tickFormat(d => d);

    svg.append("g")
        .attr("transform", `translate(${margin.left}, ${height - margin.bottom})`)
        .call(xAxis)
        .selectAll("text")
        .style("font-size", "10px")
        .attr("transform", "rotate(-45)")
        .style("text-anchor", "end");
    */
}