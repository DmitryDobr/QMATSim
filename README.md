# QMatSim
QGIS plugin that provodes tools to create MATSim basic input XML files

### About MATSim
MATSim is an open-source framework for large-scale agent-based transport simulations.

Minimally, MATSim needs the files:
- config.xml, containing the configuration options for MATSim scenario modeling,
- network.xml, with the description of the (road) network,
- population.xml, providing information about travel demand, i.e., list of agents and their daily plans.

More at [https://matsim.org](https://matsim.org).

## Available tools
### Network XML builder
This tool creates basic network XML-file with nodes and links from vector layers:
- point vector layer, where every point is unique node with unique id
- line vector layer, where every line represents link between two nodes

### Agents generator
This tool creates basic population XML-file from given network, activity points and generation parameters:
- Network
  - point vector layer, where every point is unique node with unique id
  - line vector layer, where every line represents link between two nodes
- Activities
  - point vector layer, where every point represents agents activity point
  - agents settings (number of agents, ranges of acts per plan and settings for first and last acts)
  - activities time settings (ranges of the extent of each type of activity)
