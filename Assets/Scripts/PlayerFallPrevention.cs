using System.Reflection;
using Unity.XR.CoreUtils;
using UnityEngine;

/// <summary>
/// Stops the XR Origin from falling. The Starter Assets rig applies gravity via
/// Gravity Provider + Continuous Move; this scene only needs teleport/stand.
/// Also keeps the Floor from falling if it has a dynamic Rigidbody.
/// </summary>
[DefaultExecutionOrder(-90)]
public class PlayerFallPrevention : MonoBehaviour
{
    [Tooltip("If the XR Origin drops below this world Y, snap back to the start pose.")]
    [SerializeField] float fallResetY = -0.5f;

    Vector3 startPosition;
    Quaternion startRotation;
    bool capturedStart;

    void Awake()
    {
        CaptureStartPose();
        DisableLocomotionGravity();
        StabilizeFloor();
    }

    void OnEnable()
    {
        CaptureStartPose();
    }

    void LateUpdate()
    {
        if (!capturedStart)
            return;

        if (transform.position.y < fallResetY)
            transform.SetPositionAndRotation(startPosition, startRotation);
    }

    /// <summary>
    /// Call after intentionally moving the XR Origin (e.g. in-app height adjust)
    /// so this script does not snap the rig back to an outdated pose.
    /// </summary>
    public void RecaptureStartPose()
    {
        CaptureStartPose();
    }

    void CaptureStartPose()
    {
        startPosition = transform.position;
        startRotation = transform.rotation;
        capturedStart = true;
    }

    void DisableLocomotionGravity()
    {
        var behaviours = GetComponentsInChildren<MonoBehaviour>(true);
        for (int i = 0; i < behaviours.Length; i++)
        {
            var mb = behaviours[i];
            if (mb == null)
                continue;

            SetUseGravity(mb, false);

            // Starter Assets child "Gravity" (Gravity Provider) is what pulls the rig down.
            if (mb.gameObject.name == "Gravity")
                mb.enabled = false;
        }

        var origin = GetComponent<XROrigin>();
        if (origin != null && origin.Origin != null)
        {
            var cc = origin.Origin.GetComponent<CharacterController>();
            if (cc != null)
            {
                // Cancel any leftover downward motion without removing the component.
                cc.Move(Vector3.zero);
            }
        }
    }

    static void SetUseGravity(Component component, bool value)
    {
        var type = component.GetType();
        const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;

        var prop = type.GetProperty("useGravity", flags);
        if (prop != null && prop.CanWrite && prop.PropertyType == typeof(bool))
            prop.SetValue(component, value);

        var field = type.GetField("m_UseGravity", flags);
        if (field != null && field.FieldType == typeof(bool))
            field.SetValue(component, value);
    }

    static void StabilizeFloor()
    {
        var floor = GameObject.Find("Floor") ?? GameObject.Find("Plane");
        if (floor == null)
            return;

        var rb = floor.GetComponent<Rigidbody>();
        if (rb == null)
            return;

        rb.useGravity = false;
        rb.isKinematic = true;
        rb.linearVelocity = Vector3.zero;
        rb.angularVelocity = Vector3.zero;
        rb.Sleep();
    }
}
