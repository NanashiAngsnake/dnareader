# -*- coding: utf-8 -*-
import time

def prepare(con):
    return


def _confirmees_par_compte(con, accords_requis: int, contestations_max: int):
    lignes = con.execute("""
        SELECT auteur.compte, COUNT(*)
          FROM corrections c
          JOIN (SELECT correction, compte,
                       ROW_NUMBER() OVER (PARTITION BY correction
                                          ORDER BY quand ASC) AS rang
                  FROM voix WHERE sens > 0) auteur
            ON auteur.correction = c.id AND auteur.rang = 1
         WHERE (SELECT COUNT(*) FROM voix v
                 WHERE v.correction = c.id AND v.sens > 0) >= ?
           AND (SELECT COUNT(*) FROM voix v
                 WHERE v.correction = c.id AND v.sens < 0) < ?
         GROUP BY auteur.compte""", (accords_requis, contestations_max)).fetchall()
    return {compte: n for compte, n in lignes}


def etat(con, compte: str, accords_requis: int, contestations_max: int) -> dict:
    tous = _confirmees_par_compte(con, accords_requis, contestations_max)
    confirmees = tous.get(compte, 0)
    en_attente = con.execute("""
        SELECT COUNT(*) FROM voix v
         WHERE v.compte = ? AND v.sens > 0
           AND (SELECT COUNT(*) FROM voix w
                 WHERE w.correction = v.correction AND w.sens > 0) < ?""",
        (compte, accords_requis)).fetchone()[0]
    return {"compte": compte, "confirmees": confirmees, "en_attente": en_attente}
