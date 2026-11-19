"""Safe QGIS-console action for accepting one assisted proposal."""
from qgis.core import QgsFeature, QgsMessageLog, Qgis, QgsProject

def _notify(message, level=Qgis.Info):
    QgsMessageLog.logMessage(str(message), "GeoRaster seed annotation", level)
    qgis_iface = globals().get("iface")
    if qgis_iface is not None:
        try:
            qgis_iface.messageBar().pushMessage("GeoRaster", str(message), level=level, duration=6)
        except Exception:
            pass
    print(message)

def _proposal_layers(project):
    return [layer for layer in project.mapLayers().values() if "ASSISTED_PROPOSALS" in layer.name().upper()]

def _target_layer(project, patch_id):
    wanted = str(patch_id).upper()
    candidates = [layer for layer in project.mapLayers().values() if wanted in layer.name().upper() and "SEED_GROUND_TRUTH" in layer.name().upper()]
    return candidates[0] if len(candidates) == 1 else None

def accept_selected_proposal():
    """Copy exactly one selected assisted proposal into its seed GT layer."""
    project = QgsProject.instance()
    try:
        selected = []
        for layer in _proposal_layers(project):
            selected.extend((layer, feature) for feature in layer.selectedFeatures())
        if not selected:
            _notify("Aucune proposition ASSISTED_PROPOSALS sélectionnée.", Qgis.Warning)
            return False
        if len(selected) != 1:
            _notify("Sélection multiple détectée : sélectionnez exactement une proposition.", Qgis.Warning)
            return False
        proposal_layer, proposal = selected[0]
        fields = proposal_layer.fields()
        patch_i = fields.indexOf("patch_id")
        proposal_i = fields.indexOf("proposal_id")
        source_i = fields.indexOf("source_class")
        patch_id = proposal[patch_i] if patch_i >= 0 else None
        proposal_id = proposal[proposal_i] if proposal_i >= 0 else str(proposal.id())
        source_class = proposal[source_i] if source_i >= 0 else "C_ONLY"
        if not patch_id:
            _notify("La proposition sélectionnée ne contient pas de patch_id.", Qgis.Critical)
            return False
        target = _target_layer(project, patch_id)
        if target is None or not target.isValid():
            _notify("Couche SEED_GROUND_TRUTH introuvable pour le patch %s." % patch_id, Qgis.Critical)
            return False
        if target.crs().authid() != "EPSG:32637":
            _notify("CRS cible inattendu : %s." % target.crs().authid(), Qgis.Critical)
            return False
        target_fields = target.fields(); new_feature = QgsFeature(target_fields); new_feature.setGeometry(proposal.geometry())
        values = {"building_id": str(proposal_id), "patch_id": str(patch_id), "proposal_id": str(proposal_id), "annotation_source": {"C_AND_F":"ASSISTED_C_AND_F","C_ONLY":"ASSISTED_C","F_ONLY":"ASSISTED_F"}.get(str(source_class), "ASSISTED_C"), "review_status":"ACCEPTED", "annotator":"human"}
        for name, value in values.items():
            index = target_fields.indexOf(name)
            if index >= 0: new_feature.setAttribute(index, value)
        was_editing = target.isEditable()
        if not was_editing and not target.startEditing():
            _notify("La couche cible ne peut pas passer en mode édition.", Qgis.Critical)
            return False
        if not target.addFeature(new_feature):
            if not was_editing: target.rollBack()
            _notify("La copie de la proposition a échoué.", Qgis.Critical)
            return False
        if not target.commitChanges():
            if target.isEditable(): target.rollBack()
            _notify("La sauvegarde de la couche cible a échoué.", Qgis.Critical)
            return False
        target.updateExtents(); project.setDirty(True)
        project_saved = bool(project.fileName()) and project.write()
        _notify("Proposition %s acceptée dans %s. Projet sauvegardé: %s." % (proposal_id, target.name(), project_saved))
        return True
    except Exception as exc:
        _notify("Erreur pendant l'acceptation : %s" % exc, Qgis.Critical)
        return False

# No code runs on import. Call accept_selected_proposal() from the QGIS console.
