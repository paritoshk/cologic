import Exa from "exa-js";

const exa = new Exa(process.env.EXA_API_KEY);

const query = process.argv.slice(2).join(" ") || "verilog FSM example";

const { results } = await exa.search(query, {
  type: "auto",
  numResults: 10,
  contents: { highlights: true },
});

for (const r of results) {
  console.log(`\n${r.title}\n${r.url}`);
  r.highlights?.forEach((h) => console.log(`  • ${h}`));
}
