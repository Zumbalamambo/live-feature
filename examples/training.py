from __future__ import print_function

import random
import tensorflow as tf
import logging
import live_feature_tf as lftf
import my_live_features

def input_fn(dataset):
    iterator = dataset.make_one_shot_iterator()
    next_elem = iterator.get_next()
    print(iterator.output_shapes)
    print(iterator.output_types)
    label = next_elem.pop('baz')
    return next_elem, label

def print_output_shapes(prefix, dataset):
    elem = dataset.make_one_shot_iterator().get_next()
    print("== %s ==\n%s" %(prefix, str(elem)))

def get_dataset():
    x = {}
    x['id'] = tf.constant(["Q%04d" % i for i in xrange(100)])
    x['baz'] = tf.constant([random.random() for _ in xrange(100)])
    dataset = tf.contrib.data.Dataset.from_tensor_slices(x)
    dataset = dataset.batch(8)
    print_output_shapes("after batch", dataset)
    expander = lftf.Expander('id', my_live_features, cache_fn=None)
    dataset = expander.transform(dataset)
    print_output_shapes("after expander", dataset)
    return dataset

def model_fn(features, labels, mode, params):
    w = tf.get_variable('weight', dtype=tf.float32, shape=[])
    b = tf.get_variable('bias', dtype=tf.float32, shape=[])
    loss = None
    train_op = None
    predictions = {}
    # NOTE(kjchavez): The feature 'foo' is a LIVE feature.
    predictions['baz_hat'] =  w * tf.to_float(features['foo']) + b
    if mode == tf.estimator.ModeKeys.TRAIN or mode == tf.estimator.ModeKeys.EVAL:
        err = predictions['baz_hat'] - labels
        print("err:", err.shape)
        loss = tf.reduce_mean(tf.square(err), 0)

    if mode == tf.estimator.ModeKeys.TRAIN:
        opt = tf.train.GradientDescentOptimizer(1e-6)
        train_op = opt.minimize(loss, global_step=tf.train.get_or_create_global_step())

    outputs = {tf.saved_model.signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY:
                              tf.estimator.export.PredictOutput(predictions)}
    return tf.estimator.EstimatorSpec(
            mode=mode,
            predictions=predictions,
            loss=loss,
            export_outputs=outputs,
            train_op=train_op)

def receiver_fn_from_dataset(dataset, default_batch_size=None, label_keys=None):
    iterator = dataset.make_one_shot_iterator()
    next_elem = iterator.get_next()
    print(iterator.output_shapes)
    print(iterator.output_types)
    if label_keys:
        for key in label_keys:
            next_elem.pop(key)

    print(next_elem)
    return tf.estimator.export.build_raw_serving_input_receiver_fn(
            next_elem,
            default_batch_size=default_batch_size)

def run():
    tf.logging.set_verbosity(tf.logging.INFO)
    estimator = tf.estimator.Estimator(model_fn)
    dataset = get_dataset()
    estimator.train(lambda: input_fn(dataset), steps=10)
    estimator.evaluate(lambda: input_fn(dataset), steps=10)
    receiver_fn = receiver_fn_from_dataset(dataset, label_keys=['baz'])
    estimator.export_savedmodel("/tmp/exportdir", receiver_fn)

if __name__ == "__main__":
    run()
