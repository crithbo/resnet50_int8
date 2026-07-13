from __future__ import annotations


PROFILE_POLICIES = {
    "batch": {
        ("DequantizeLinear", "Flatten"): "zero_copy_proved",
        ("Flatten", "QuantizeLinear"): "layout_compatible_rebase_w7",
        ("QuantizeLinear", "QLinearConv"): "explicit_relayout",
        ("QuantizeLinear", "QLinearMatMul"): "exact_alias_proved",
        ("QLinearConv", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "MaxPool"): "exact_alias_proved",
        ("MaxPool", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearGlobalAveragePool"): "exact_alias_proved",
        ("QLinearGlobalAveragePool", "DequantizeLinear"): "layout_compatible_rebase_w7",
        ("QLinearMatMul", "QLinearAdd"): "exact_alias_proved",
        ("QLinearAdd", "DequantizeLinear"): "layout_compatible_rebase_w7",
    },
    "ring_channel": {
        ("DequantizeLinear", "Flatten"): "zero_copy_proved",
        ("Flatten", "QuantizeLinear"): "layout_compatible_rebase_w7",
        ("QuantizeLinear", "QLinearConv"): "explicit_relayout",
        ("QuantizeLinear", "QLinearMatMul"): "explicit_relayout",
        ("QLinearConv", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "MaxPool"): "exact_alias_proved",
        ("MaxPool", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearConv", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearAdd"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearConv"): "layout_compatible_rebase_w7",
        ("QLinearAdd", "QLinearGlobalAveragePool"): "exact_alias_proved",
        ("QLinearGlobalAveragePool", "DequantizeLinear"): "explicit_relayout",
        ("QLinearMatMul", "QLinearAdd"): "exact_alias_proved",
        ("QLinearAdd", "DequantizeLinear"): "explicit_relayout",
    },
}
