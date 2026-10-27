"""Moteur de parcours : d'une demande comprise à une sélection expliquée, sur le catalogue publié — sans IA, avec les
règles de l'ontologie (deals/ontology). Il ne lit ni n'écrit rien lui-même : l'ontologie dit les règles, le catalogue
publié les faits (caractéristiques et leur provenance) et l'offre (prix, remise) ; ici, on décide et on dit pourquoi.

  Plan(domaine, besoins)   ce qui est exigé sans exception (un besoin éliminatoire : laver le sol) et ce qui est préféré
                           (un besoin fort : les poils ; faible : l'appartement), en critères pondérés
  plan.judge(attrs)        un produit : écarté (un critère éliminatoire qui vaut 0, et pourquoi) ou admis, avec son
                           adéquation (oui 1, en partie 0,5, inconnu 0,25, non 0, pondérés) et ses explications (fait, source)
  plan.rank(lignes, clé)   les admis : d'abord ceux qui satisfont tout à fait le plus de critères forts, puis les mieux
                           adaptés, puis l'ordre demandé (les meilleures affaires, ou le prix) ; inconnu n'est pas non : un
                           produit dont la fiche ne dit rien reste montré, après ceux dont on sait qu'ils conviennent
  question(…)              la question utile quand la demande est vague (ni type, ni besoin, ni caractéristique) : posée
                           seulement si au moins deux réponses donnent des sélections vraiment différentes ; jamais pour
                           une demande précise, et elle ne bloque rien (la sélection est montrée dessous)
  suggest(…)               un autre type quand celui demandé ne peut pas répondre à un besoin (« un robot ne monte pas les
                           marches »), avec sa raison ; la sélection reste celle du type demandé, rien n'est imposé
"""
from .ontology import UNKNOWN_SCORE, WEIGHTS

TOP = 6                                                    # une sélection : ce qu'un écran de téléphone montre
CHANGED = 3                                                # une réponse change la sélection : au plus 3 des 6 premiers en commun
WHY_SHOWN = 2                                              # explications par carte (ce qu'une carte montre)


class Verdicts:
    """Les faits et les verdicts des critères, par produit, gardés le temps d'une publication (ils ne changent qu'à la
    nuit) ; et, par besoin, les produits qui le satisfont tout à fait (les nombres d'Affiner et d'Explorer)."""
    def __init__(self, domain):
        self.d, self._facts, self._v, self._good = domain, {}, {}, {}

    def facts(self, pid, attrs):
        f = self._facts.get(pid)
        if f is None:
            f = self._facts[pid] = self.d.facts(attrs)
        return f

    def of(self, pid, attrs, c):
        v = self._v.get((pid, c))
        if v is None:
            v = self._v[pid, c] = self.d.judge(c, (attrs or {}).get("sub"), self.facts(pid, attrs))
        return v

    def good(self, need, rows):
        """Les produits (parmi rows : product_id, attrs) qui satisfont tout à fait le besoin need ; gardé par besoin."""
        known = self._good.setdefault(need, {})
        plan = None
        for r in rows:
            if r["product_id"] not in known:
                plan = plan or Plan(self.d, [need])
                j = plan.judge(r["attrs"], r["product_id"], self)
                known[r["product_id"]] = not j["out"] and j["met"] >= len(plan.strong) > 0
        return {r["product_id"] for r in rows if known[r["product_id"]]}


class Plan:
    def __init__(self, domain, needs=(), drop=()):
        """needs : les besoins demandés (clés), dans l'ordre où ils sont dits ; drop : des critères à ne pas appliquer
        (ceux qu'un type demandé ne peut pas satisfaire, dits à part)."""
        self.d = domain
        self.needs = [n for n in dict.fromkeys(needs) if n in domain.needs]
        weight, strict, order = {}, set(), []
        for n in self.needs:
            for c, w in domain.needs[n]["criteria"].items():
                if c in drop:
                    continue
                weight[c] = max(weight.get(c, 0), WEIGHTS[w])
                if w == "eliminatoire":
                    strict.add(c)
                if c not in order:
                    order.append(c)
        rank = lambda c: (c not in strict, weight[c] < 1)
        self.order = sorted(order, key=rank)               # éliminatoires, puis forts, puis faibles ; dans l'ordre dit
        self.weight, self.strict = weight, strict
        self.strong = [c for c in self.order if weight[c] >= 1]

    def __bool__(self):
        return bool(self.order)

    def judge(self, attrs, pid=None, verdicts=None):
        """→ {out: raison d'être écarté ou None, met: critères forts tout à fait satisfaits, fit: adéquation (0 à 1), why}
        verdicts : les verdicts gardés de la publication (Verdicts), pour le produit pid."""
        d, attrs = self.d, attrs or {}
        if verdicts is None:
            facts, sub = d.facts(attrs), attrs.get("sub")
            verdict = lambda c: d.judge(c, sub, facts)
        else:
            verdict = lambda c: verdicts.of(pid, attrs, c)
        why, total, got, met, out = [], 0.0, 0.0, 0, None
        for c in self.order:
            score, text, src, _, best = verdict(c)
            if c in self.strict and score == 0 and out is None:
                out = text
            w = self.weight[c]
            total += w
            got += w * (UNKNOWN_SCORE * best if score is None else score)   # inconnu : selon ce qu'il peut encore valoir
            met += c in self.strong and score == 1
            why.append({"c": c, "v": score, "text": text, "src": src})
        return {"out": out, "met": met, "fit": round(got / total, 3) if total else 0.0, "why": why}

    def rank(self, rows, key, verdicts=None):
        """Les lignes admises, les mieux adaptées d'abord puis selon key ; → (admises, {produit: jugement}, écartées :
        {raison: nombre})."""
        seen, kept, dropped = {}, [], {}
        for r in rows:
            j = self.judge(r["attrs"], r["product_id"], verdicts)
            if j["out"]:
                dropped[j["out"]] = dropped.get(j["out"], 0) + 1
                continue
            seen[r["product_id"]] = j
            kept.append(r)
        kept.sort(key=lambda r: (-seen[r["product_id"]]["met"], -seen[r["product_id"]]["fit"], key(r)))
        return kept, seen, dropped


def conflict(domain, sub, needs, weak=False):
    """Les critères qu'un type ne peut pas satisfaire, quel que soit le produit (une règle de type à 0 : « un robot ne
    monte pas les marches ») → [(critère, raison, besoin)] ; weak : les critères faibles aussi (ils ne s'appliquent pas
    non plus, mais ne valent pas qu'on propose un autre type)."""
    out = []
    if sub not in domain.sub:
        return out
    for n in needs:
        for c, w in domain.needs[n]["criteria"].items():
            if w == "faible" and not weak:
                continue
            rule = next((r for r in domain.criteria[c]["rules"] if set(r["if"]) == {"sub"} and sub in r["if"]["sub"]), None)
            if rule is not None and rule["score"] == 0:
                out.append((c, rule["say"], n))
    return out


def suggest(domain, sub, needs, count):
    """Un autre type pour un besoin que le type demandé ne peut pas satisfaire : celui que le besoin suggère d'abord
    (hint), puis l'ordre des sous-familles, parmi ceux où le critère peut valoir 1 et qui ont des produits (count : type →
    nombre de produits admis par le reste de la demande). → {sub, label, why, count} ou None."""
    for c, why, n in conflict(domain, sub, needs):
        crit = domain.criteria[c]
        able = lambda s: any(r["score"] == 1 and s in r["if"].get("sub", [s]) for r in crit["rules"])
        order = list(domain.needs[n].get("hint", ())) + [s["key"] for s in domain.subs]
        for s in dict.fromkeys(order):
            if s != sub and able(s) and count.get(s):
                return {"sub": s, "label": domain.sub[s]["plural"], "why": why, "count": count[s]}
    return None


def question(domain, rows, current, key, when, verdicts=None):
    """La question utile pour une demande vague, ou None. rows : les produits admis par le reste de la demande ; current
    : les 6 premiers montrés ; when : « sub » (aucun type demandé) ou « need » (un type, aucun besoin). Une réponse est
    gardée si elle a des produits qui lui conviennent et change la sélection (au plus 3 des 6 premiers en commun) ; la
    question n'est posée que si au moins deux réponses le font."""
    q = next((x for x in domain.questions if x["when"] == when), None)
    if q is None:
        return None
    now, options = set(current[:TOP]), []
    for o in q["options"]:
        a = o["apply"]
        if "sub" in a:
            pool = [r for r in rows if (r["attrs"] or {}).get("sub") == a["sub"]]
            top, good = [r["product_id"] for r in sorted(pool, key=key)[:TOP]], len(pool)
        else:
            plan = Plan(domain, [a["need"]])
            kept, seen, _ = plan.rank(rows, key, verdicts)
            top = [r["product_id"] for r in kept[:TOP]]
            good = sum(seen[r["product_id"]]["met"] >= len(plan.strong) > 0 for r in kept)
        if good and len(now & set(top)) <= CHANGED:
            options.append({"label": o["label"], "small": o.get("small"), "apply": {"domain": domain.key, **a}, "count": good})
    if len(options) < 2:
        return None
    return {"key": q["key"], "text": q["text"], "options": options}
