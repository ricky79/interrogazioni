// Tiene i nomi e abbrevia il cognome: "Anna Maria De Luca" → "Anna Maria D."
const PARTICELLE = new Set(["de", "di", "da", "del", "della", "dei", "degli", "dal", "dalla",
                            "lo", "la", "li", "van", "von", "d'"]);

function abbrevia(nome) {
  const parti = nome.trim().split(/\s+/);
  if (parti.length < 2) return nome.trim();
  if (/^\p{L}\.$/u.test(parti[parti.length - 1])) return parti.join(" ");  // già abbreviato
  let inizio = parti.length - 1;  // prima parola del cognome
  while (inizio > 1 && PARTICELLE.has(parti[inizio - 1].toLowerCase())) inizio--;
  return parti.slice(0, inizio).join(" ") + " " + parti[inizio][0].toUpperCase() + ".";
}

document.querySelectorAll(".abbrevia").forEach((btn) => {
  btn.addEventListener("click", () => {
    const form = btn.closest("form");
    const area = form.querySelector(`textarea[name="${btn.dataset.target}"]`);
    if (area) area.value = area.value.split("\n").map((r) => (r.trim() ? abbrevia(r) : r)).join("\n");
    // nella pagina della classe abbrevia anche i nomi già salvati
    form.querySelectorAll('.riga-alunno input[name^="nome_"]').forEach((i) => { i.value = abbrevia(i.value); });
  });
});
