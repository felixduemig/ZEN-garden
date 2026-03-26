# ZEN-Garden Architecture - Mermaid Diagrams

## 1. Execution Flow (Main Process)

```mermaid
flowchart TD
    A[User runs zen-garden --dataset=X] --> B[__main__.py]
    B --> C[runner.py run()]

    C --> D[Load config.json]
    D --> E[Validate dataset exists]
    E --> F[Extract scenarios]

    F --> G{For each scenario}
    G --> H[Create OptimizationSetup]

    H --> I{For each rolling horizon step}
    I --> J[construct_optimization_problem()]

    J --> K[Initialize linopy Model]
    K --> L[Reset component registries]
    L --> M[Element.construct_model_components()]

    M --> N[construct_sets()]
    N --> O[construct_parameters()]
    O --> P[construct_variables()]
    P --> Q[construct_constraints()]

    Q --> R[Apply scaling if enabled]
    R --> S[solve() - Call solver]
    S --> T{Check optimality}
    T --> U[Postprocess results]
    U --> V[Save to HDF5/JSON]

    V --> W[Next horizon step?]
    W -->|Yes| I
    W -->|No| X[Next scenario?]
    X -->|Yes| G
    X -->|No| Y[Done]
```

## 2. Component Hierarchy (Class Diagram)

```mermaid
classDiagram
    class OptimizationSetup {
        +model: linopy.Model
        +sets: IndexSet
        +variables: Variable
        +parameters: Parameter
        +constraints: Constraint
        +dict_elements: dict
        +construct_optimization_problem()
        +solve()
    }

    class Element {
        <<abstract>>
        +construct_model_components()
        +construct_sets()
        +construct_parameters()
        +construct_variables()
        +construct_constraints()
    }

    class Carrier {
        +constraint_import_export_balance()
        +constraint_emissions_limit()
        +constraint_carbon_budget()
    }

    class Technology {
        <<abstract>>
    }

    class ConversionTechnology {
        +constraint_demand()
        +constraint_flows()
        +constraint_capacity_operation()
        +constraint_capex_pwa()
        +constraint_efficiency()
    }

    class TransportTechnology {
        +constraint_flows_edges()
        +constraint_transmission_losses()
        +constraint_transport_cost_pwa()
    }

    class StorageTechnology {
        +constraint_storage_level_evolution()
        +constraint_storage_initial_level()
        +constraint_roundtrip_efficiency()
    }

    class EnergySystem {
        +time_steps: TimeStepsDicts
        +unit_handling: UnitHandling
        +data_input: DataInput
    }

    class IndexSet {
        +set_nodes
        +set_edges
        +set_technologies
        +set_carriers
        +set_time_steps
    }

    OptimizationSetup --> EnergySystem
    OptimizationSetup --> Element
    Element <|-- Carrier
    Element <|-- Technology
    Technology <|-- ConversionTechnology
    Technology <|-- TransportTechnology
    Technology <|-- StorageTechnology
    OptimizationSetup --> IndexSet
```

## 3. Data Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    participant CSV as Input CSV/JSON Files
    participant PP as preprocess/extract_input_data.py
    participant EL as Element Objects
    participant MC as model/component.py
    participant LM as linopy Model
    participant SOL as Solver
    participant POST as postprocess/postprocess.py

    CSV->>PP: Read system.json, demand.csv, attributes.json
    PP->>PP: Convert units (Pint), aggregate time-series
    PP->>EL: Create Carrier/Technology objects with data

    EL->>MC: construct_sets() - Create indices
    MC->>LM: Register IndexSet (nodes, technologies, time)

    EL->>MC: construct_parameters() - Extract attributes
    MC->>LM: Register Parameters (costs, efficiencies, demand)

    EL->>MC: construct_variables() - Create decision vars
    MC->>LM: Register Variables (capacity, flow, storage)

    EL->>MC: construct_constraints() - Build equations
    MC->>LM: Register Constraints (balance, limits, efficiency)

    LM->>SOL: Export to LP/MPS format
    SOL->>SOL: Optimize (Gurobi/HiGHS)
    SOL->>LM: Return solution

    LM->>POST: Extract variable values
    POST->>POST: Convert to physical units
    POST->>CSV: Save to HDF5, JSON, CSV
```

## 4. Constraint Building Process (State Diagram)

```mermaid
stateDiagram-v2
    [*] --> InitializeModel: construct_optimization_problem()

    InitializeModel --> BuildSets: construct_sets()
    BuildSets --> BuildParameters: construct_parameters()
    BuildParameters --> BuildVariables: construct_variables()
    BuildVariables --> BuildConstraints: construct_constraints()

    BuildConstraints --> ConversionConstraints: ConversionTechnology constraints
    BuildConstraints --> TransportConstraints: TransportTechnology constraints
    BuildConstraints --> StorageConstraints: StorageTechnology constraints
    BuildConstraints --> CarrierConstraints: Carrier constraints

    ConversionConstraints --> EnergyBalance: constraint_demand()
    EnergyBalance --> CapacityLimits: constraint_capacity_operation()
    CapacityLimits --> PWACapex: constraint_capex_pwa() ⚠️ SOS2 Variables
    PWACapex --> Efficiency: constraint_efficiency()

    TransportConstraints --> EdgeFlows: constraint_flows_edges()
    EdgeFlows --> Losses: constraint_transmission_losses()
    Losses --> TransportPWA: constraint_transport_cost_pwa()

    StorageConstraints --> LevelEvolution: constraint_storage_level_evolution()
    LevelEvolution --> InitialLevel: constraint_storage_initial_level()
    InitialLevel --> RoundtripEff: constraint_roundtrip_efficiency()

    CarrierConstraints --> ImportExport: constraint_import_export_balance()
    ImportExport --> Emissions: constraint_emissions_limit()
    Emissions --> CarbonBudget: constraint_carbon_budget()

    Efficiency --> Scaling: Apply scaling (optional)
    TransportPWA --> Scaling
    RoundtripEff --> Scaling
    CarbonBudget --> Scaling

    Scaling --> ReadyToSolve: Model complete
    ReadyToSolve --> [*]
```

## 5. File Structure Overview

```mermaid
graph TD
    subgraph "Input Data Structure"
        A[system.json]
        B[energy_system/]
        C[set_carriers/]
        D[set_technologies/]

        B --> B1[attributes.json]
        B --> B2[base_units.json]
        B --> B3[set_edges.csv]
        B --> B4[set_nodes.csv]
        B --> B5[unit_definitions.txt]

        C --> C1[electricity/]
        C --> C2[heat/]
        C --> C3[natural_gas/]

        C1 --> C1a[demand.csv]
        C1 --> C1b[availability_import.csv]
        C1 --> C1c[prices.csv]

        D --> D1[set_conversion_technologies/]
        D --> D2[set_storage_technologies/]
        D --> D3[set_transport_technologies/]

        D1 --> D1a[coal_plant/]
        D1 --> D1b[gas_plant/]
        D1 --> D1c[solar/]

        D1a --> D1a1[attributes.json]
        D1a --> D1a2[capacity_existing.csv]
        D1a --> D1a3[opex_variable.csv]
    end

    subgraph "Code Structure"
        E[zen_garden/]
        E --> E1[__main__.py]
        E --> E2[runner.py]
        E --> E3[optimization_setup.py]

        E --> F[preprocess/]
        F --> F1[extract_input_data.py]

        E --> G[model/]
        G --> G1[element.py]
        G --> G2[component.py]
        G --> G3[energy_system.py]

        G --> H[technology/]
        H --> H1[conversion_technology.py]
        H --> H2[transport_technology.py]
        H --> H3[storage_technology.py]

        G --> I[carrier/]
        I --> I1[carrier.py]

        E --> J[postprocess/]
        J --> J1[postprocess.py]
    end

    subgraph "Output Structure"
        K[outputs/dataset_name/]
        K --> K1[analysis.json]
        K --> K2[param_dict.h5]
        K --> K3[scenarios.json]
        K --> K4[set_dict.h5]
        K --> K5[solver.json]
        K --> K6[var_dict.h5]

        K --> L[solver_files/]
        L --> L1[model.lp]
        L --> L2[model.mps]
    end
```

## 6. Key Methods Call Flow

```mermaid
flowchart LR
    subgraph "Entry Point"
        A[runner.py run()]
    end

    subgraph "Scenario Loop"
        B[For each scenario]
        C[OptimizationSetup()]
    end

    subgraph "Horizon Loop"
        D[For each horizon step]
        E[construct_optimization_problem()]
    end

    subgraph "Model Building"
        F[Element.construct_model_components()]
        G[construct_sets()]
        H[construct_parameters()]
        I[construct_variables()]
        J[construct_constraints()]
    end

    subgraph "Technology Constraints"
        K[ConversionTechnology.construct_constraints()]
        L[TransportTechnology.construct_constraints()]
        M[StorageTechnology.construct_constraints()]
    end

    subgraph "Solver & Results"
        N[solve()]
        O[Postprocess]
    end

    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
    J --> K
    J --> L
    J --> M
    K --> N
    L --> N
    M --> N
    N --> O
```

## Usage Instructions

1. **Copy each Mermaid code block** into a Mermaid-compatible tool:
   - [Mermaid Live Editor](https://mermaid.live/)
   - GitHub/GitLab (supports Mermaid natively)
   - VS Code with Mermaid extension
   - Draw.io (import Mermaid)
   - Notion, Obsidian, etc.

2. **For Draw.io import**:
   - Go to Draw.io
   - File → Import → Mermaid

3. **For documentation**:
   - These diagrams show the complete ZEN-garden architecture
   - Flowcharts show execution order
   - Class diagrams show inheritance
   - Sequence diagrams show data flow
   - State diagrams show constraint building process</content>
<parameter name="filePath">c:\Users\felix\Documents\GitHub\ZEN-garden\ZEN_Garden_Architecture_Diagrams.md