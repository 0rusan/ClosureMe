using UnityEngine;
using UnityEngine.XR;

public class ControlModeSwitcher : MonoBehaviour
{
    [Header("PC (Desktop)")]
    public Camera pcCamera;          // 你場景裡的 PC 用 Camera
    public Behaviour pcMove;         // moveCon (可留空)
    public Behaviour pcLook;         // lookCon (可留空)

    [Header("VR")]
    public GameObject xrOrigin;      // XR Origin (VR) 根物件
    public Behaviour vrMoveProvider; // ContinuousMoveProvider / ActionBased…其一
    public Behaviour vrTurnProvider; // SnapTurnProvider 或 ContinuousTurnProvider

    [Header("Override (測試用)")]
    public bool forcePC = false;
    public bool forceVR = false;

    void Start() { Apply(); }

    public void Apply()
    {
        bool vrActive = XRSettings.enabled && XRSettings.isDeviceActive;
        if (forcePC) vrActive = false;
        if (forceVR) vrActive = true;

        // VR on / off
        if (xrOrigin) xrOrigin.SetActive(vrActive);
        if (vrMoveProvider) vrMoveProvider.enabled = vrActive;
        if (vrTurnProvider) vrTurnProvider.enabled = vrActive;

        // PC on / off
        if (pcCamera) pcCamera.gameObject.SetActive(!vrActive);
        if (pcMove) pcMove.enabled = !vrActive;
        if (pcLook) pcLook.enabled = !vrActive;

        // 避免雙 AudioListener
        var vrCam = xrOrigin ? xrOrigin.GetComponentInChildren<AudioListener>(true) : null;
        if (vrCam) vrCam.enabled = vrActive;
        var pcListener = pcCamera ? pcCamera.GetComponent<AudioListener>() : null;
        if (pcListener) pcListener.enabled = !vrActive;

        Debug.Log($"[Mode] {(vrActive ? "VR" : "PC")} controls enabled.");
    }
}