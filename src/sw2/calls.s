    .section .patch_d5b2, "ax"
    .code 16
    tjl hook_set_adv
    .section .patch_d5ba, "ax"
    .code 16
    tjl hook_set_scanrsp
    .section .patch_d768, "ax"
    .code 16
    tjl hook_set_gatt
    .section .patch_d570, "ax"
    .code 16
    tjl hook_prepare_address
    .section .patch_d5be, "ax"
    .code 16
    tjl hook_bond_count
    .section .patch_d74c, "ax"
    .code 16
    tjl hook_reports
    .section .patch_d750, "ax"
    .code 16
    tjl hook_pair_button
    .section .patch_d48a, "ax"
    .code 16
    tjl hook_request_mtu
    .section .patch_d496, "ax"
    .code 16
    tjl hook_request_parameters
    .section .patch_18f5e, "ax"
    .code 16
    tjl hook_l2cap
    .section .patch_17270, "ax"
    .code 16
    tjl hook_ll_receive
    .section .patch_1705a, "ax"
    .code 16
    tjl hook_feature_response
    .section .patch_d9ba, "ax"
    .code 16
    tjl hook_stock_radio_loop
