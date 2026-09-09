from graphviz import Digraph

g = Digraph("architecture", format="png")
g.attr(rankdir="TB", bgcolor="#0E1117", splines="polyline", nodesep="0.7", ranksep="0.8")
g.attr("node", shape="box", style="filled,rounded", fontname="Helvetica",
       fontsize="14", fontcolor="#FAFAFA", color="#4A5568", fillcolor="#1C2333",
       penwidth="1.5", margin="0.25,0.15")
g.attr("edge", fontname="Helvetica", fontsize="12", fontcolor="#CBD5E0",
       color="#718096", penwidth="1.3", arrowsize="0.8")

# Nodes
g.node("A", "User's question")
g.node("B", "LLM generates SQL")
g.node("C", "Validator", shape="diamond", fillcolor="#2D3748", margin="0.2,0.15")
g.node("X", "Refused, reason shown", fillcolor="#4A2020", color="#9B4444")
g.node("D", "Read-only DB\n10s timeout")
g.node("E", "Table + chart + summary", fillcolor="#1F3A2E", color="#4A9B6E")
g.node("F", "Retry once\n(back to LLM step)")

# Edges
g.edge("A", "B")
g.edge("B", "C")
g.edge("B", "X", label="destructive, out of\nscope, or impossible")
g.edge("C", "X", label="not SELECT, or\nunknown table/column")
g.edge("C", "D", label="passes")
g.edge("D", "E", label="success")
g.edge("D", "F", label="execution error")


g.render("/home/claude/olist_project/screenshots/architecture", cleanup=True)
print("rendered")
