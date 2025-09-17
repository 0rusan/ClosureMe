/*using UnityEngine;

public class DoorController : MonoBehaviour
{
    public Transform door; // 拖曳門的 Transform
    public float openAngle = 90f;
    public float openSpeed = 2f;

    private bool isPlayerNear = false;
    private bool isOpen = false;
    private Quaternion closedRotation;
    private Quaternion openRotation;

    void Start()
    {
        closedRotation = door.rotation;
        openRotation = door.rotation * Quaternion.Euler(0, openAngle, 0);
    }

    void Update()
    {
        if (isPlayerNear && Input.GetKeyDown(KeyCode.E))
        {
            isOpen = !isOpen;
        }

        if (isOpen)
        {
            door.rotation = Quaternion.Slerp(door.rotation, openRotation, Time.deltaTime * openSpeed);
        }
        else
        {
            door.rotation = Quaternion.Slerp(door.rotation, closedRotation, Time.deltaTime * openSpeed);
        }
    }

    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            isPlayerNear = true;
            Debug.Log("靠近門，按E開關");
        }
    }

    private void OnTriggerExit(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            isPlayerNear = false;
        }
    }
}*/
using UnityEngine;

[RequireComponent(typeof(Collider))]
public class DoorController : MonoBehaviour
{
    // ← 新增：讓 VRInputBridge 能知道「最近的門」
    public static DoorController Current;

    [Header("Door Parts")]
    public Transform door;

    [Header("Motion")]
    public float openAngle = 90f;
    public float openSpeed = 2f;
    public Vector3 axis = Vector3.up;

    [Header("Debug")]
    public bool isOpen = false;
    public bool isPlayerNear = false;

    Quaternion _closedLocalRot;
    Quaternion _openLocalRot;

    void Reset()
    {
        var c = GetComponent<Collider>();
        c.isTrigger = true; // 感應區
    }

    void Start()
    {
        if (door == null) door = transform;
        _closedLocalRot = door.localRotation;
        _openLocalRot = _closedLocalRot * Quaternion.AngleAxis(openAngle, axis.normalized);
    }

    void Update()
    {
        // PC：E 鍵互動（可留著）
        if (isPlayerNear && Input.GetKeyDown(KeyCode.E))
            Interact();

        // 平滑旋轉
        var target = isOpen ? _openLocalRot : _closedLocalRot;
        door.localRotation = Quaternion.Slerp(door.localRotation, target, Time.deltaTime * openSpeed);
    }

    // —— 共用入口（PC/VR 都走這裡）——
    public void Interact()
    {
        if (!isPlayerNear) return;
        isOpen = !isOpen;
        // 可加音效/動畫事件
    }

    public void VR_ToggleDoor() => Interact();

    // —— 感應區 ——（只要 XR Origin 的 Collider 進來且 Tag=Player）
    void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            isPlayerNear = true;
            Current = this;       // ← 新增：把自己註冊成目前靠近的門
        }
    }

    void OnTriggerExit(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            isPlayerNear = false;
            if (Current == this)  // ← 新增：只有自己是 Current 才清空
                Current = null;
        }
    }
}