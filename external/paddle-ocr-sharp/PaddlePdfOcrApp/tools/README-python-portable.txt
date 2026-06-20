Bundled Python for machines without Python installed
====================================================

1) On a developer PC with internet, run (from PaddlePdfOcrApp folder):

   powershell -ExecutionPolicy Bypass -File tools\Prepare-PythonPortable.ps1

2) This creates folder: PaddlePdfOcrApp\python_portable\

3) When you publish the app (single-file or folder), COPY the whole
   python_portable folder next to PaddlePdfOcrApp.exe.

4) The app will use python_portable\python.exe automatically when
   appsettings.local.json does not set a valid PythonExePath.

Note: First run may download ONNX models into the user profile cache;
ensure target PCs can write to %USERPROFILE% or set model paths per RapidOCR docs.
