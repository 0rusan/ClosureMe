#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using UnityEditor.AssetImporters;
using System.IO;

public class AutoHumanoidImporter : AssetPostprocessor
{
    // 僅監看這個資料夾
    private static readonly string WatchFolder = "Assets/AgentModels/Incoming/";

    void OnPreprocessModel()
    {
        if (!assetPath.Replace('\\', '/').StartsWith(WatchFolder)) return;

        var mi = (ModelImporter)assetImporter;

        // 僅使用「本模型」建立 Humanoid
        mi.animationType = ModelImporterAnimationType.Human;
        mi.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;

        // 關掉會造成骨架缺失/合併的選項
        mi.optimizeGameObjects = false;   // 取消 Optimize Game Objects

        // 其他不必要物件也可不匯入（選擇性）
        mi.importCameras = false;
        mi.importLights = false;

        // 材質相關（維持你原本的設定）
        mi.materialImportMode = ModelImporterMaterialImportMode.ImportStandard;
        mi.materialLocation = ModelImporterMaterialLocation.External;
        mi.materialName = ModelImporterMaterialName.BasedOnTextureName;
        mi.materialSearch = ModelImporterMaterialSearch.Everywhere;
    }

    void OnPostprocessModel(GameObject go)
    {
        if (!assetPath.Replace('\\', '/').StartsWith(WatchFolder)) return;

        // 僅做檢查與提示（不做 CopyFromOtherAvatar）
        var anim = go.GetComponentInChildren<Animator>();
        if (anim == null || anim.avatar == null || !anim.avatar.isHuman)
        {
            Debug.LogError(
                $"[AutoHumanoidImporter] {Path.GetFileName(assetPath)} 未成功建立 Humanoid Avatar。" +
                $"請確認模型骨架與命名，或手動在 Import 設為 Humanoid 後再 Reimport。"
            );
        }

        // 延遲覆蓋 Prefab（避免同幀操作資源導致報錯）
        EditorApplication.delayCall += () => PostProcessAfterImport(assetPath);
    }

    private static void PostProcessAfterImport(string modelPath)
    {
        var prefabDir = "Assets/Resources/Agents";
        Directory.CreateDirectory(prefabDir);
        var prefabPath = $"{prefabDir}/AIAgentModel.prefab";

        var src = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
        if (src == null) { Debug.LogError($"Importer 無法讀取模型：{modelPath}"); return; }

        var temp = Object.Instantiate(src);
        temp.name = "AIAgentModel";

        PrefabUtility.SaveAsPrefabAsset(temp, prefabPath, out bool ok);
        Object.DestroyImmediate(temp);

        if (ok) Debug.Log($"[AutoHumanoidImporter] 覆蓋 Prefab：{prefabPath}");
        else Debug.LogError($"[AutoHumanoidImporter] 覆蓋失敗：{prefabPath}");
    }
}
#endif