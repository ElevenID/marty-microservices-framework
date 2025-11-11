# Statistical Analysis Features

This microservice template includes comprehensive statistical analysis capabilities built on top of popular Python data science libraries. The analytics features are exposed through gRPC endpoints, making it easy to integrate statistical analysis into your microservice architecture.

## Features

### 📊 Data Generation

- **Sample Data Generation**: Creates realistic synthetic datasets for testing and demonstration
- **Configurable Parameters**: Control sample size, random seed, and data characteristics
- **Multiple Data Types**: Includes numeric, categorical, and correlated variables

### 📈 Statistical Analysis

- **Descriptive Statistics**: Mean, median, standard deviation, quartiles, skewness, kurtosis
- **Correlation Analysis**: Pearson correlation matrix with automatic strong correlation detection
- **Distribution Analysis**: Normality tests, Q-Q plots, histograms, box plots
- **Clustering Analysis**: K-means clustering with PCA visualization and silhouette scoring

### 📋 Visualization

- **Automatic Plot Generation**: All analyses include publication-ready visualizations
- **Base64 Encoding**: Plots are returned as base64 strings for easy integration
- **Multiple Plot Types**: Heatmaps, scatter plots, histograms, box plots, and distribution plots

## Dependencies

The following packages are included for statistical analysis:

```toml
# Statistical analysis dependencies
"pandas>=2.1.0",        # Data manipulation and analysis
"numpy>=1.24.0",        # Numerical computing
"scipy>=1.11.0",        # Statistical functions
"matplotlib>=3.7.0",    # Basic plotting
"seaborn>=0.12.0",      # Statistical visualization
"plotly>=5.15.0",       # Interactive plots
"scikit-learn>=1.3.0"   # Machine learning algorithms
```

## gRPC Endpoints

### GenerateSampleData

Generate synthetic datasets for testing and demonstration.

**Request:**

```protobuf
message SampleDataRequest {
  int32 n_samples = 1;  // Number of samples to generate (default: 1000)
  int32 seed = 2;       // Random seed for reproducibility (default: 42)
}
```

**Response:**

```protobuf
message SampleDataResponse {
  string data_csv = 1;   // Generated data in CSV format
  string message = 2;    // Success message
}
```

**Example Usage:**

```python
response = await stub.GenerateSampleData(
    greeter_pb2.SampleDataRequest(n_samples=1000, seed=42)
)
df = pd.read_csv(io.StringIO(response.data_csv))
```

### AnalyzeCorrelation

Perform correlation analysis on a dataset.

**Request:**

```protobuf
message CorrelationRequest {
  string data_csv = 1;  // Dataset in CSV format
}
```

**Response:**

```protobuf
message AnalysisResponse {
  bool success = 1;           // Success indicator
  string message = 2;         // Status message
  string results_json = 3;    // Analysis results as JSON
  string plot_base64 = 4;     // Correlation heatmap as base64 PNG
}
```

**Results JSON Structure:**

```json
{
  "correlation_matrix": {
    "variable1": {"variable1": 1.0, "variable2": 0.75},
    "variable2": {"variable1": 0.75, "variable2": 1.0}
  },
  "strong_correlations": [
    {
      "variable_1": "income",
      "variable_2": "spending",
      "correlation": 0.85,
      "strength": "strong positive"
    }
  ]
}
```

### AnalyzeClustering

Perform K-means clustering analysis with PCA visualization.

**Request:**

```protobuf
message ClusteringRequest {
  string data_csv = 1;  // Dataset in CSV format
  int32 n_clusters = 2; // Number of clusters (default: 3)
}
```

**Results JSON Structure:**

```json
{
  "n_clusters": 3,
  "silhouette_score": 0.65,
  "cluster_summary": {
    "cluster_0": {
      "size": 350,
      "percentage": 35.0,
      "means": {"age": 32.5, "income": 45000}
    }
  },
  "pca_explained_variance": [0.4, 0.3],
  "n_samples": 1000
}
```

### AnalyzeDistribution

Analyze the statistical distribution of numeric data.

**Request:**

```protobuf
message DistributionRequest {
  repeated double values = 1;  // Numeric values to analyze
  string column_name = 2;      // Name for the variable
}
```

**Results JSON Structure:**

```json
{
  "descriptive_stats": {
    "count": 1000,
    "mean": 35.2,
    "median": 34.8,
    "std_dev": 9.7,
    "min": 18.0,
    "max": 80.0,
    "quartiles": {"q1": 28.3, "q2": 34.8, "q3": 42.1},
    "skewness": 0.15,
    "kurtosis": -0.8
  },
  "normality_tests": {
    "shapiro_wilk": {
      "statistic": 0.998,
      "p_value": 0.045,
      "is_normal": false
    }
  }
}
```

## Demo Script

Run the included demo to see all analytics features in action:

```bash
# Start the service
make run

# In another terminal, run the demo
./examples/analytics_demo.py
```

The demo will:

1. Generate a sample dataset with 1000 rows
2. Perform correlation analysis and save a heatmap
3. Run K-means clustering with visualization
4. Analyze the distribution of age data
5. Save all plots as PNG files

## Integration Examples

### Using with pandas

```python
import pandas as pd
import io

# Generate data
response = await stub.GenerateSampleData(
    greeter_pb2.SampleDataRequest(n_samples=500)
)
df = pd.read_csv(io.StringIO(response.data_csv))

# Analyze correlations
corr_response = await stub.AnalyzeCorrelation(
    greeter_pb2.CorrelationRequest(data_csv=response.data_csv)
)
```

### Saving Plots

```python
import base64

if analysis_response.plot_base64:
    image_data = base64.b64decode(analysis_response.plot_base64)
    with open("analysis_plot.png", "wb") as f:
        f.write(image_data)
```

### Processing Results

```python
import json

if response.success:
    results = json.loads(response.results_json)
    correlations = results.get("strong_correlations", [])
    for corr in correlations:
        print(f"{corr['variable_1']} ↔ {corr['variable_2']}: {corr['correlation']:.3f}")
```

## Extending Analytics

To add new statistical methods:

1. **Add to AnalyticsService**: Implement your method in `src/microservice_template/service/analytics.py`
2. **Update Protobuf**: Add new message types and RPC methods in `proto/greeter.proto`
3. **Regenerate Stubs**: Run `make proto` to update gRPC code
4. **Implement Endpoint**: Add the handler in `src/microservice_template/service/greeter.py`
5. **Add Tests**: Create tests in `tests/unit/` and `tests/integration/`

## Performance Considerations

- **Memory Usage**: Large datasets are processed in-memory; consider streaming for very large data
- **CPU Intensive**: Statistical computations are CPU-bound; consider async patterns for I/O
- **Plot Generation**: Matplotlib operations are blocking; plots are generated synchronously
- **Caching**: Consider caching computed results for repeated analyses

## Monitoring

Analytics operations are automatically instrumented with:

- **OpenTelemetry Tracing**: Each analysis operation creates spans
- **Prometheus Metrics**: Request counts, latencies, and error rates
- **Structured Logging**: Detailed logs for debugging and auditing
- **Health Checks**: Service health monitoring included

## Security

- **Input Validation**: All inputs are validated before processing
- **Resource Limits**: Consider implementing limits on dataset sizes
- **Error Handling**: Comprehensive error handling prevents service crashes
- **Data Privacy**: No data is persisted; all processing is stateless
