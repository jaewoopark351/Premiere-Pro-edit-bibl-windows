// Premiere Pro FCP7 XML import smoke test for the Windows port.
// Run from Premiere Pro with: Adobe Premiere Pro.exe -r scripts/premiere_import_smoke.jsx

var root = "C:/Vtuber_Souorce_Code/Claude/Premiere-Pro-edit-bibl-windows";
var xmlPath = root + "/output/test.mp4_cut.xml";
var projectPath = root + "/output/premiere_import_smoke.prproj";
var logPath = root + "/output/premiere_import_smoke_result.txt";

function writeLog(lines) {
    var f = new File(logPath);
    f.encoding = "UTF-8";
    f.open("w");
    for (var i = 0; i < lines.length; i++) {
        f.writeln(lines[i]);
    }
    f.close();
}

var lines = [];
try {
    lines.push("premiere_import_smoke=started");
    lines.push("xml=" + xmlPath);
    var xmlFile = new File(xmlPath);
    lines.push("xml_exists=" + xmlFile.exists);

    if (!xmlFile.exists) {
        throw new Error("XML file not found");
    }

    if (app.newProject) {
        lines.push("newProject_available=true");
        app.newProject(projectPath);
    } else {
        lines.push("newProject_available=false");
    }

    var imported = false;
    if (app.project && app.project.importFiles) {
        imported = app.project.importFiles([xmlPath], true, app.project.rootItem, false);
        lines.push("importFiles_return=" + imported);
    } else {
        lines.push("importFiles_available=false");
    }

    if (app.project && app.project.sequences) {
        lines.push("sequence_count=" + app.project.sequences.numSequences);
    }

    if (app.project && app.project.saveAs) {
        app.project.saveAs(projectPath);
        lines.push("project_saved=" + projectPath);
    }

    lines.push("premiere_import_smoke=finished");
} catch (e) {
    lines.push("premiere_import_smoke=error");
    lines.push("error=" + e.toString());
}

writeLog(lines);
