using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Optional standing-height calibration: right thumbstick Y raises/lowers the XR Origin.
/// Page Up / Page Down also work in the editor. Recaptures PlayerFallPrevention's
/// safe pose after each adjustment so the fall fix is not undone.
/// </summary>
public class PlayerHeightAdjust : MonoBehaviour
{
    [SerializeField] float metersPerSecond = 0.75f;
    [SerializeField] float stickDeadzone = 0.25f;
    [SerializeField] float minWorldY = -0.4f;
    [SerializeField] float maxWorldY = 2.5f;

    InputAction stickAction;
    CharacterController characterController;
    PlayerFallPrevention fallPrevention;

    void Awake()
    {
        characterController = GetComponent<CharacterController>();
        fallPrevention = GetComponent<PlayerFallPrevention>();
    }

    void OnEnable()
    {
        stickAction = new InputAction("PlayerHeightAdjust", InputActionType.Value, expectedControlType: "Vector2");
        stickAction.AddBinding("<XRController>{RightHand}/thumbstick");
        stickAction.Enable();
    }

    void OnDisable()
    {
        if (stickAction == null)
            return;
        stickAction.Disable();
        stickAction.Dispose();
        stickAction = null;
    }

    void Update()
    {
        float y = 0f;
        if (stickAction != null)
        {
            float stickY = stickAction.ReadValue<Vector2>().y;
            if (Mathf.Abs(stickY) >= stickDeadzone)
                y = stickY;
        }

        Keyboard keyboard = Keyboard.current;
        if (keyboard != null)
        {
            if (keyboard.pageUpKey.isPressed)
                y = 1f;
            else if (keyboard.pageDownKey.isPressed)
                y = -1f;
        }

        if (Mathf.Abs(y) < 0.01f)
            return;

        float delta = y * metersPerSecond * Time.deltaTime;
        Vector3 pos = transform.position;
        pos.y = Mathf.Clamp(pos.y + delta, minWorldY, maxWorldY);

        bool ccWasEnabled = characterController != null && characterController.enabled;
        if (ccWasEnabled)
            characterController.enabled = false;

        transform.position = pos;

        if (ccWasEnabled)
            characterController.enabled = true;

        if (fallPrevention != null)
            fallPrevention.RecaptureStartPose();
    }
}
